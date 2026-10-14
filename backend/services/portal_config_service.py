"""Versioned portal settings: append-only versions, optimistic concurrency, audit."""

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.portal_config import PortalConfiguracaoModel
from schemas.portal_config import ClientePortalConfig, ProdutorPortalConfig
from services import audit_service

SCHEMAS = {"cliente": ClientePortalConfig, "produtor": ProdutorPortalConfig}
MAX_VERSIONS_LISTED = 20


class PortalConfigError(Exception):
    pass


class PortalConfigInvalid(PortalConfigError):
    pass


class PortalConfigConflict(PortalConfigError):
    pass


class PortalConfigNotFound(PortalConfigError):
    pass


def _schema(portal):
    try:
        return SCHEMAS[portal]
    except KeyError:
        raise PortalConfigNotFound("Portal desconhecido.") from None


def defaults(portal) -> dict:
    return _schema(portal)().model_dump()


def validate(portal, payload) -> dict:
    try:
        return _schema(portal).model_validate(payload).model_dump()
    except ValidationError as exc:
        fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
        raise PortalConfigInvalid("Configuração inválida: " + ", ".join(fields)) from None


def _latest(db: Session, portal):
    return db.scalar(
        select(PortalConfiguracaoModel)
        .where(PortalConfiguracaoModel.portal == portal)
        .order_by(PortalConfiguracaoModel.versao.desc())
        .limit(1)
    )


def active(db: Session, portal) -> dict:
    """Return the published version, re-validated so older payloads gain new defaults."""
    _schema(portal)
    row = _latest(db, portal)
    if row is None:
        return {"portal": portal, "versao": 0, "config": defaults(portal)}
    try:
        config = validate(portal, row.dados)
    except PortalConfigInvalid:
        # A stored version that no longer validates must never break a portal.
        config = defaults(portal)
    return {"portal": portal, "versao": row.versao, "config": config}


def versions(db: Session, portal) -> list[dict]:
    _schema(portal)
    rows = db.scalars(
        select(PortalConfiguracaoModel)
        .where(PortalConfiguracaoModel.portal == portal)
        .order_by(PortalConfiguracaoModel.versao.desc())
        .limit(MAX_VERSIONS_LISTED)
    ).all()
    return [
        {
            "versao": row.versao,
            "autor_usuario_id": row.autor_usuario_id,
            "restaurada_de_versao": row.restaurada_de_versao,
            "created_at": row.created_at.isoformat() if row.created_at else "",
        }
        for row in rows
    ]


def publish(db: Session, portal, payload, *, actor, base_versao: int, restored_from=None, request_id=None):
    config = validate(portal, payload)
    current = active(db, portal)
    if base_versao != current["versao"]:
        raise PortalConfigConflict("A configuração foi alterada por outra pessoa. Recarregue antes de publicar.")
    if config == current["config"] and current["versao"] > 0:
        return current
    next_version = (db.scalar(
        select(func.max(PortalConfiguracaoModel.versao)).where(PortalConfiguracaoModel.portal == portal)
    ) or 0) + 1
    row = PortalConfiguracaoModel(
        portal=portal,
        versao=next_version,
        dados=config,
        autor_usuario_id=getattr(actor, "id", None),
        restaurada_de_versao=restored_from,
    )
    try:
        db.add(row)
        db.flush()
        audit_service.record(
            db,
            actor=actor,
            action="portal.config_restored" if restored_from else "portal.config_published",
            entity_type="portal_config",
            entity_id=row.id,
            metadata={
                "portal": portal,
                "old_version": current["versao"],
                "new_version": next_version,
                "restored_from_version": restored_from,
            },
            request_id=request_id,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise PortalConfigConflict("Outra versão foi publicada ao mesmo tempo. Recarregue e tente novamente.") from None
    return {"portal": portal, "versao": next_version, "config": config}


def restore(db: Session, portal, versao: int, *, actor, base_versao: int, request_id=None):
    _schema(portal)
    row = db.scalar(
        select(PortalConfiguracaoModel).where(
            PortalConfiguracaoModel.portal == portal,
            PortalConfiguracaoModel.versao == versao,
        )
    )
    if row is None:
        raise PortalConfigNotFound("Versão não encontrada.")
    return publish(
        db, portal, row.dados, actor=actor, base_versao=base_versao,
        restored_from=versao, request_id=request_id,
    )
