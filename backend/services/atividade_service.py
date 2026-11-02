"""Work in progress shown in the notification center ("Em andamento").

Server-side processing that a person waits for: tagged previews being generated, the
Admin's "regenerate every preview" batch, beat previews in that batch and the compression
of delivered previews. Items finished in the last minutes stay briefly as done.
"""
from datetime import datetime, timedelta, timezone

from crud.crud_producao import acesso_produtor
from models import BeatModel, PreviaTagJobModel, ProducaoArquivoModel, ProducaoModel
from services import previa_lote_service
from sqlalchemy import select

RECENTE = timedelta(minutes=10)
LIMITE = 12


def _agora():
    return datetime.now(timezone.utc)


def _item(ref, titulo, detalhe, estado, *, progresso=None, criado_em=None, concluido_em=None, tipo="previa",
          url=None, miniatura=None):
    return {"id": ref, "tipo": tipo, "titulo": titulo, "detalhe": detalhe, "estado": estado,
            "progresso": progresso, "criado_em": criado_em, "concluido_em": concluido_em, "url": url,
            "miniatura": miniatura}


def _previas(db, filtro, url_for, *, incluir_lote=False):
    """Tag jobs waiting/processing (and the ones that just finished) for the given files."""
    base = (select(PreviaTagJobModel, ProducaoArquivoModel, ProducaoModel)
            .join(ProducaoArquivoModel, ProducaoArquivoModel.id == PreviaTagJobModel.arquivo_id)
            .join(ProducaoModel, ProducaoModel.id == ProducaoArquivoModel.producao_id)
            .where(ProducaoArquivoModel.tipo == "previa", *filtro))
    if not incluir_lote:
        base = base.where(PreviaTagJobModel.lote_id.is_(None))
    pendentes = db.execute(base.where(PreviaTagJobModel.estado == "pendente")
                           .order_by(PreviaTagJobModel.lote_id.is_not(None), PreviaTagJobModel.arquivo_id)
                           .limit(LIMITE)).all()
    recentes = db.execute(base.where(PreviaTagJobModel.estado.in_(("pronto", "erro")),
                                     PreviaTagJobModel.concluido_em.is_not(None),
                                     PreviaTagJobModel.concluido_em >= _agora() - RECENTE)
                          .order_by(PreviaTagJobModel.concluido_em.desc()).limit(5)).all()
    # The worker runs one at a time, in this same order: the first is the one being processed.
    primeiro = db.scalar(select(PreviaTagJobModel.arquivo_id).where(PreviaTagJobModel.estado == "pendente")
                         .order_by(PreviaTagJobModel.lote_id.is_not(None), PreviaTagJobModel.arquivo_id).limit(1))
    itens = []
    for job, arquivo, producao in pendentes:
        processando = job.arquivo_id == primeiro
        itens.append(_item(
            f"previa:{arquivo.id}", "Gerando prévia com tag" if processando else "Prévia na fila",
            f"{arquivo.nome_exibicao} · #{producao.id} {producao.titulo}",
            "processando" if processando else "na_fila", criado_em=arquivo.created_at, url=url_for(producao)))
    for job, arquivo, producao in recentes:
        ok = job.estado == "pronto"
        itens.append(_item(
            f"previa:{arquivo.id}", "Prévia com tag pronta" if ok else "Prévia sem tag (falhou)",
            f"{arquivo.nome_exibicao} · #{producao.id} {producao.titulo}", "concluido" if ok else "erro",
            criado_em=arquivo.created_at, concluido_em=job.concluido_em, url=url_for(producao)))
    return itens


def _lote(lote):
    detalhe = f"{lote['concluidos']} de {lote['total']} prontas"
    if lote["erros"]:
        detalhe += f" · {lote['erros']} com erro"
    if lote["sem_tag"]:
        detalhe += f" · {lote['sem_tag']} sem tag cadastrada"
    return _item(f"lote:{lote['id']}", "Gerando todas as prévias de novo" if lote["em_andamento"]
                 else "Prévias geradas de novo", detalhe,
                 "processando" if lote["em_andamento"] else ("erro" if lote["erros"] else "concluido"),
                 progresso=lote["progresso"], criado_em=lote["created_at"], concluido_em=lote["concluido_em"],
                 tipo="lote_previas", url="/admin.html#section-custos")


def _compressao(db):
    from services.arquivos_admin_service import compressao_resumo

    resumo = compressao_resumo(db)
    if not resumo["pendentes"]:
        return None
    total = resumo["previas_entregues"]
    return _item("compressao", "Comprimindo prévias de produções entregues",
                 f"{resumo['comprimidas']} de {total} em MP3 {resumo['bitrate'].replace('k', ' kbps')}",
                 "processando", progresso=round(resumo["comprimidas"] / total, 4) if total else None,
                 tipo="compressao", url="/admin.html#section-arquivos")


def listar(db, user):
    itens = []
    if user.is_admin:
        lote = previa_lote_service.atual(db)
        if lote is not None:
            itens.append(_lote(lote))
        itens.extend(_previas(db, (), lambda producao: "/admin.html#section-producoes"))
        compressao = _compressao(db)
        if compressao:
            itens.append(compressao)
    elif user.role == "produtor":
        itens.extend(_previas(db, (acesso_produtor(user.id), ProducaoArquivoModel.visivel_produtor.is_(True)),
                              lambda producao: f"/produtor/producoes/{producao.id}", incluir_lote=False))
        beats = db.scalars(select(BeatModel).where(BeatModel.produtor_id == user.id,
                                                   BeatModel.previa_estado == "pendente")
                           .order_by(BeatModel.id).limit(LIMITE)).all()
        for beat in beats:
            itens.append(_item(f"beat:{beat.id}", "Atualizando a prévia do beat", beat.titulo, "na_fila",
                               criado_em=beat.created_at, tipo="beat", url="/produtor/beats",
                               miniatura=beat.capa_url or None))
    ativas = sum(1 for item in itens if item["estado"] in ("processando", "na_fila"))
    return {"itens": itens, "ativas": ativas}
