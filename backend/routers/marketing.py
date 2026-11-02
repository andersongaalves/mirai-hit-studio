"""Admin "Marketing": visits, origins, campaigns and what they turn into."""
from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from services import marketing_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/marketing", tags=["Marketing (Admin)"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]


@router.get("")
def painel(db: Db, user: Admin, dias: int = 28, atualizar: bool = False):
    if dias not in marketing_service.PERIODOS:
        raise HTTPException(422, "Escolha 7, 28 ou 90 dias.")
    return marketing_service.carregar(db, dias, atualizar=atualizar)
