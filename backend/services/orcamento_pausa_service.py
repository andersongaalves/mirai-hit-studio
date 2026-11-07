"""Pause new quote requests (busy schedule).

While paused, the public form shows a notice instead of the calculator and the API
refuses new requests; everything already in progress continues normally.
"""
from datetime import datetime, timezone

from models import ConfigModel
from services import audit_service

MENSAGEM_PADRAO = (
    "Estamos com muitos projetos em andamento e pausamos novos pedidos por alguns dias "
    "para manter a qualidade das entregas. Volte em breve!"
)


def estado(db):
    config = db.get(ConfigModel, 1)
    pausado = bool(config and config.orcamentos_pausados)
    return {
        "pausado": pausado,
        "mensagem": ((config.orcamentos_pausa_mensagem or "").strip() or MENSAGEM_PADRAO) if pausado else None,
        "mensagem_personalizada": (config.orcamentos_pausa_mensagem or None) if config else None,
        "desde": config.orcamentos_pausados_em if pausado else None,
        "mensagem_padrao": MENSAGEM_PADRAO,
    }


def definir(db, admin, pausado, mensagem=None, request_id=None):
    config = db.get(ConfigModel, 1)
    if config is None:
        config = ConfigModel(id=1)
        db.add(config)
    mensagem = " ".join((mensagem or "").split())[:500] or None
    mudou = bool(config.orcamentos_pausados) != pausado
    config.orcamentos_pausados = pausado
    config.orcamentos_pausa_mensagem = mensagem
    if mudou:
        config.orcamentos_pausados_em = datetime.now(timezone.utc) if pausado else None
    audit_service.record(
        db, actor=admin, action="budget.intake_paused" if pausado else "budget.intake_resumed",
        entity_type="config", entity_id=1, metadata={"mensagem_personalizada": bool(mensagem)},
        request_id=request_id,
    )
    db.commit()
    return estado(db)
