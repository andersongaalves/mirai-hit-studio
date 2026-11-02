"""Admin "Marketing": visits, origins, campaigns and what they turn into."""
from typing import Annotated, Literal

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends
from services import marketing_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/admin/marketing", tags=["Marketing (Admin)"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]


@router.get("")
def painel(db: Db, user: Admin, dias: Literal[7, 28, 90] = 28, atualizar: bool = False):
    return marketing_service.carregar(db, dias, atualizar=atualizar)
