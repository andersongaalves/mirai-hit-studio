"""Roadmap 5.17: the largest eligible discount wins; discounts never stack."""
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

from models.config import ConfigModel
from schemas.promocao import Promocao
from services import audit_service


def desconto_global(db):
    config = db.query(ConfigModel).order_by(ConfigModel.id).first()
    value = Decimal(str(config.desconto if config is not None else 0))
    if not value.is_finite() or not Decimal(0) <= value <= Decimal(100):
        raise ValueError("invalid_catalog_discount")
    return value


def preco(model, global_percentual=Decimal(0), *, agora=None):
    agora = agora or datetime.now(timezone.utc)
    global_percentual = Decimal(str(global_percentual))
    if not global_percentual.is_finite() or not Decimal(0) <= global_percentual <= Decimal(100):
        raise ValueError("invalid_catalog_discount")
    promocao = Promocao.model_validate(model.promocao) if model.promocao is not None else None
    ativa = bool(promocao and promocao.ativa and (promocao.inicio is None or agora >= promocao.inicio)
                 and (promocao.fim is None or agora < promocao.fim))
    global_elegivel = global_percentual if model.aplica_desconto else Decimal(0)
    percentual = max(global_elegivel, promocao.percentual if ativa else Decimal(0))
    base = Decimal(str(model.preco_base if hasattr(model, "preco_base") else model.valor_base))
    return {
        "preco_vigente": (base * (Decimal(1) - percentual / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        "desconto_percentual": percentual,
        "promocao_ativa": ativa,
    }


def auditar_alteracao(db, model, anterior, *, actor=None, request_id=None):
    if anterior == model.promocao:
        return
    metadata = {}
    for prefix, config in (("old", anterior), ("new", model.promocao)):
        for key, field in (("percent", "percentual"), ("active", "ativa"), ("start", "inicio"), ("end", "fim")):
            metadata[f"{prefix}_promotion_{key}"] = (config or {}).get(field)
    audit_service.record(db, actor=actor, action="catalog.promotion_changed",
                         entity_type="combo" if hasattr(model, "preco_base") else "service", entity_id=model.id,
                         metadata=metadata, request_id=request_id)
