"""AUD6-S09-002: one page per producer for the Admin (read-only, no new permissions).

Productions from test chains stay out, matching the sections' default view.
"""
from datetime import datetime, timezone

from models import BeatModel, OrcamentoModel, ProducaoModel, UsuarioModel
from sqlalchemy import func, or_, select

FINAIS = ("finalizado", "entregue")
LIMITE = 20


class ProdutorNaoEncontrado(Exception):
    pass


def _aware(value):
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def carregar(db, produtor_id, *, agora=None):
    agora = agora or datetime.now(timezone.utc)
    produtor = db.get(UsuarioModel, produtor_id)
    if produtor is None or produtor.role != "produtor":
        raise ProdutorNaoEncontrado("Produtor não encontrado.")
    teste = select(OrcamentoModel.id).where(OrcamentoModel.is_test.is_(True))
    producoes = db.scalars(
        select(ProducaoModel)
        .where(ProducaoModel.produtor_id == produtor_id,
               or_(ProducaoModel.orcamento_id.is_(None), ~ProducaoModel.orcamento_id.in_(teste)))
        .order_by(ProducaoModel.id.desc())
    ).all()
    ativas = [p for p in producoes if p.status not in FINAIS]
    atrasadas = [p for p in ativas if p.prazo_entrega and _aware(p.prazo_entrega) < agora]
    beats = dict(db.execute(
        select(BeatModel.status, func.count()).where(BeatModel.produtor_id == produtor_id).group_by(BeatModel.status)
    ).all())
    return {
        "produtor": {
            "id": produtor.id,
            "username": produtor.username,
            "nome_exibicao": produtor.nome_exibicao,
            "ativo": bool(produtor.ativo),
            "painel_beats": bool(produtor.painel_beats),
            "especialidades": [item for item in (produtor.especialidades or "").split(",") if item],
        },
        "contagens": {
            "producoes_ativas": len(ativas),
            "producoes_atrasadas": len(atrasadas),
            "producoes_finalizadas": len(producoes) - len(ativas),
            "beats_em_revisao": int(beats.get("revisao", 0)),
            "beats_aprovados": int(beats.get("aprovado", 0)),
            "beats_vendidos": int(beats.get("vendido", 0)),
            "beats_rejeitados": int(beats.get("rejeitado", 0)),
        },
        "producoes": [
            {"id": p.id, "titulo": p.titulo, "cliente": p.cliente, "status": p.status,
             "prazo_entrega": p.prazo_entrega, "atrasada": p in atrasadas}
            for p in (ativas + [p for p in producoes if p.status in FINAIS])[:LIMITE]
        ],
    }
