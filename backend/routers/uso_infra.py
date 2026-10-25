from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends
from services import uso_infra_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/uso", tags=["Uso da infraestrutura"])


@router.get("")
def uso(db: Annotated[Session, Depends(get_db)], atualizar: bool = False, user=Depends(require_admin)):
    # Admin only; the payload carries numbers and status text, never credentials.
    return uso_infra_service.carregar(db, atualizar=atualizar)
