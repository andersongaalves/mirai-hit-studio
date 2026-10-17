from typing import Annotated

from core.dependencies import get_current_user
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from schemas.portal_notificacao import (
    NotificacaoResponse,
    NotificacoesResponse,
    NotificacoesVistas,
)
from services import portal_notificacao_service as service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/portal/notificacoes", tags=["Notificacoes dos portais"])


def require_portal_user(user=Depends(get_current_user)):
    if user.is_admin or user.role not in {"cliente", "produtor"} or (user.role == "cliente" and not user.cliente_id):
        raise HTTPException(status_code=403, detail="Acesso restrito ao seu portal.")
    return user


Db = Annotated[Session, Depends(get_db)]
User = Annotated[object, Depends(require_portal_user)]


@router.get("", response_model=NotificacoesResponse)
def listar(db: Db, user: User, antes_id: Annotated[int | None, Query(gt=0)] = None,
           limite: Annotated[int, Query(ge=1, le=50)] = 30, somente_nao_vistas: bool = False):
    return service.listar(db, user, antes_id=antes_id, limite=limite, somente_nao_vistas=somente_nao_vistas)


@router.post("/vistas", response_model=list[NotificacaoResponse])
def marcar_vistas(dados: NotificacoesVistas, db: Db, user: User):
    return service.marcar_vistas(db, user, dados.ids)
