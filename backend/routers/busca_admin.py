from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, Query
from services import busca_admin_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/busca", tags=["Busca do Admin"])


@router.get("")
def buscar(
    db: Annotated[Session, Depends(get_db)],
    q: Annotated[str, Query(min_length=2, max_length=80)],
    user: Annotated[object, Depends(require_admin)],
):
    # AUD6-S09-006: Admin only; read-only and limited to five results per kind.
    return busca_admin_service.buscar(db, q)
