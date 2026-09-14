from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from schemas.audit_log import AuditLogPage
from services import audit_service


router = APIRouter(prefix="/audit-logs", tags=["Auditoria"])


@router.get("", response_model=AuditLogPage)
def listar_auditoria(
    action: str | None = Query(default=None, min_length=1, max_length=80),
    entity_type: str | None = Query(default=None, min_length=1, max_length=50),
    entity_id: str | None = Query(default=None, min_length=1, max_length=64),
    actor_user_id: int | None = Query(default=None, gt=0),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return audit_service.list_page(
        db,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
