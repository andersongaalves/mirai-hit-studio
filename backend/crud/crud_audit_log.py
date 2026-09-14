from datetime import datetime

from sqlalchemy.orm import Session

from models.audit_log import AuditLogModel
from models.usuario import UsuarioModel


def listar(
    db: Session,
    *,
    action: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    actor_user_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 25,
):
    query = db.query(AuditLogModel, UsuarioModel.username).outerjoin(
        UsuarioModel,
        AuditLogModel.actor_user_id == UsuarioModel.id,
    )
    if action:
        query = query.filter(AuditLogModel.action == action)
    if entity_type:
        query = query.filter(AuditLogModel.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditLogModel.entity_id == entity_id)
    if actor_user_id is not None:
        query = query.filter(AuditLogModel.actor_user_id == actor_user_id)
    if date_from:
        query = query.filter(AuditLogModel.created_at >= date_from)
    if date_to:
        query = query.filter(AuditLogModel.created_at <= date_to)

    total = query.count()
    rows = (
        query.order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return rows, total
