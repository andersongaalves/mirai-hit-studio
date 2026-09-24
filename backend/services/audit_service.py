from math import ceil

from sqlalchemy.orm import Session

from crud import crud_audit_log
from models.audit_log import AuditLogModel


ALLOWED_METADATA = {
    "old_status",
    "new_status",
    "old_role",
    "new_role",
    "old_active",
    "new_active",
    "total_sent",
    "total_failed",
    "total_skipped",
    "old_mode",
    "new_mode",
    "new_assigned_user_id",
    "channel",
}


def sanitize_metadata(metadata: dict | None):
    safe = {}
    for key, value in (metadata or {}).items():
        if key not in ALLOWED_METADATA or not isinstance(value, (str, int, float, bool, type(None))):
            continue
        safe[key] = value[:100] if isinstance(value, str) else value
    return safe


def record(
    db: Session,
    *,
    actor,
    action: str,
    entity_type: str,
    entity_id=None,
    metadata: dict | None = None,
    request_id: str | None = None,
):
    actor_id = getattr(actor, "id", actor if isinstance(actor, int) else None)
    if not isinstance(actor_id, int):
        actor_id = None
    entry = AuditLogModel(
        actor_user_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        metadata_json=sanitize_metadata(metadata),
        request_id=request_id[:64] if request_id else None,
    )
    db.add(entry)
    db.flush()
    return entry


def list_page(db: Session, **filters):
    rows, total = crud_audit_log.listar(db, **filters)
    page = filters.get("page", 1)
    page_size = filters.get("page_size", 25)
    return {
        "items": [
            {
                "id": entry.id,
                "actor_user_id": entry.actor_user_id,
                "actor_username": username,
                "action": entry.action,
                "entity_type": entry.entity_type,
                "entity_id": entry.entity_id,
                "metadata": entry.metadata_json or {},
                "request_id": entry.request_id,
                "created_at": entry.created_at,
            }
            for entry, username in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }
