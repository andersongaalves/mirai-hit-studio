"""Admin: regenerate every tagged preview of the site in a queue.

Production previews go back to the tag queue (with the responsible producer's tag and the
current studio settings) and beats get a queue flag; the single worker processes one item
at a time, new uploads first, so the site keeps answering. Previews keep playing their
previous tagged version until the new one replaces it. Progress is counted live.
"""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from models import (
    BeatModel,
    PreviaLoteModel,
    PreviaTagJobModel,
    ProducaoArquivoModel,
    ProducaoModel,
)
from services import audio_tag_service, audit_service
from sqlalchemy import func, select

RECENTE = timedelta(hours=24)


def _agora():
    return datetime.now(timezone.utc)


def ativo(db):
    return db.scalar(select(PreviaLoteModel).where(PreviaLoteModel.concluido_em.is_(None))
                     .order_by(PreviaLoteModel.id.desc()).limit(1))


def iniciar(db, actor, request_id=None):
    if ativo(db) is not None:
        raise HTTPException(409, "Ja existe uma geracao de previas em andamento.")
    lote = PreviaLoteModel(autor_usuario_id=actor.id, total=0, sem_tag=0)
    db.add(lote)
    db.flush()
    total = sem_tag = 0
    jobs = db.execute(
        select(PreviaTagJobModel, ProducaoArquivoModel, ProducaoModel)
        .join(ProducaoArquivoModel, ProducaoArquivoModel.id == PreviaTagJobModel.arquivo_id)
        .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
        .where(ProducaoArquivoModel.tipo == "previa", PreviaTagJobModel.estado.in_(("pronto", "erro")))
        .order_by(PreviaTagJobModel.arquivo_id)
        .with_for_update(of=PreviaTagJobModel, skip_locked=True)
    ).all()
    for job, model, production in jobs:
        if audio_tag_service.enfileirar_regeneracao(db, job, model, production, lote_id=lote.id) is False:
            sem_tag += 1
        else:
            total += 1
    beats = db.scalars(select(BeatModel).where(BeatModel.original_ref.is_not(None),
                                               BeatModel.previa_estado.is_distinct_from("pendente"))
                       .with_for_update(skip_locked=True)).all()
    for beat in beats:
        beat.previa_estado = "pendente"
        beat.previa_lote_id = lote.id
        total += 1
    lote.total, lote.sem_tag = total, sem_tag
    if total == 0:
        lote.concluido_em = _agora()
    audit_service.record(db, actor=actor, action="audio_tag.previews_batch_started", entity_type="previa_lote",
                         entity_id=lote.id, metadata={"total": total, "sem_tag": sem_tag}, request_id=request_id)
    db.commit()
    audio_tag_service.sinalizar_fila()
    return resumo(db, lote)


def _contagem(db, lote_id):
    jobs = dict(db.execute(select(PreviaTagJobModel.estado, func.count()).where(PreviaTagJobModel.lote_id == lote_id)
                           .group_by(PreviaTagJobModel.estado)).all())
    beats = dict(db.execute(select(BeatModel.previa_estado, func.count()).where(BeatModel.previa_lote_id == lote_id)
                            .group_by(BeatModel.previa_estado)).all())
    pendentes = jobs.get("pendente", 0) + beats.get("pendente", 0)
    erros = jobs.get("erro", 0) + beats.get("erro", 0)
    return pendentes, erros


def resumo(db, lote):
    if lote is None:
        return None
    pendentes, erros = _contagem(db, lote.id)
    concluidos = max(0, lote.total - pendentes)
    return {
        "id": lote.id,
        "total": lote.total,
        "concluidos": concluidos,
        "erros": erros,
        "pendentes": pendentes,
        "sem_tag": lote.sem_tag,
        "progresso": round(concluidos / lote.total, 4) if lote.total else 1.0,
        "em_andamento": lote.concluido_em is None,
        "created_at": lote.created_at,
        "concluido_em": lote.concluido_em,
    }


def atual(db):
    """The running batch, else the last one finished in the past day (shown as done)."""
    lote = ativo(db)
    if lote is None:
        lote = db.scalar(select(PreviaLoteModel).where(PreviaLoteModel.concluido_em >= _agora() - RECENTE)
                         .order_by(PreviaLoteModel.id.desc()).limit(1))
    return resumo(db, lote)


def fechar_concluidos(session_factory):
    """Worker: close running batches that have nothing left in the queue."""
    with session_factory() as db:
        lote = ativo(db)
        if lote is None:
            return
        pendentes, _ = _contagem(db, lote.id)
        if pendentes == 0:
            lote.concluido_em = _agora()
            db.commit()
