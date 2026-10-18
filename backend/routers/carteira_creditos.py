from typing import Annotated

from core.dependencies import require_admin, require_client
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Response
from models import ClienteModel
from schemas.credito_servico import CarteiraCreditosResponse
from services import carteira_creditos_service as service
from sqlalchemy.orm import Session

router = APIRouter(tags=["Creditos de servicos"])
Db = Annotated[Session, Depends(get_db)]
Client = Annotated[object, Depends(require_client)]
Admin = Annotated[object, Depends(require_admin)]


@router.get("/portal/cliente/creditos", response_model=CarteiraCreditosResponse)
def meus_creditos(response: Response, db: Db, user: Client):
    response.headers["Cache-Control"] = "private, no-store"
    cliente = db.get(ClienteModel, user.cliente_id)
    if cliente is None or not cliente.ativo:
        raise HTTPException(403, "Acesso do cliente indisponivel.")
    return service.carteira(db, user.cliente_id)


@router.get("/clientes/{cliente_id}/creditos", response_model=CarteiraCreditosResponse)
def creditos_cliente(cliente_id: int, response: Response, db: Db, user: Admin):
    response.headers["Cache-Control"] = "private, no-store"
    if db.get(ClienteModel, cliente_id) is None:
        raise HTTPException(404, "Cliente nao encontrado.")
    return service.carteira(db, cliente_id)
