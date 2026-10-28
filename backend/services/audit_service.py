from math import ceil

from crud import crud_audit_log
from models.audit_log import AuditLogModel
from sqlalchemy.orm import Session

ALLOWED_METADATA = {
    "old_status",
    "stage_order",
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
    "old_assigned_user_id",
    "channel",
    "old_amount",
    "new_amount",
    "reference_changed",
    "receipt_changed",
    "client_id",
    "proposal_id",
    "result",
    "orcamento_id",
    # Etapa 07 (S06): beat license events and the operator's stated reason.
    "beat_id",
    "reason",
    "old_is_test",
    "new_is_test",
    "old_client_is_test",
    "financial_history_confirmed",
    "portal",
    "old_version",
    "new_version",
    "restored_from_version",
    "old_stage_count",
    "new_stage_count",
    "review_round",
    "extra_review",
    "policy_keys",
    "changed_keys",
    "old_promotion_percent", "new_promotion_percent",
    "old_promotion_active", "new_promotion_active",
    "old_promotion_start", "new_promotion_start",
    "old_promotion_end", "new_promotion_end",
    # Etapa 07 (S10): financial context and the operator's stated reason.
    "reason",
    "charge_status", "production_status",
    "charge_old_status", "charge_new_status",
    # S08: private audio-tag configuration and temporary preview diagnostics.
    "scope", "version", "interval", "volume", "tag_id",
    "nivelamento_automatico", "alvo_relativo_db", "ganho_min_db", "ganho_max_db",
    "silencio_lufs", "limiter_dbfs",
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
