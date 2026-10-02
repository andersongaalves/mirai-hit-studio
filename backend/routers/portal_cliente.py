from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import require_client
from database import get_db
from models.usuario import UsuarioModel
from schemas.portal_cliente import FinanceiroClienteResponse, ProducaoClienteResponse
from services import financial_service, portal_cliente_service

router = APIRouter(prefix="/portal/cliente", tags=["Portal do Cliente"])
Db = Annotated[Session, Depends(get_db)]
CurrentClient = Annotated[UsuarioModel, Depends(require_client)]


@router.get("/producoes", response_model=list[ProducaoClienteResponse])
def listar_minhas_producoes(db: Db, user: CurrentClient):
    return portal_cliente_service.listar_producoes(db, user.cliente_id)


@router.get("/producoes/historico", response_model=list[ProducaoClienteResponse])
def listar_meu_historico(db: Db, user: CurrentClient):
    return portal_cliente_service.listar_historico(db, user.cliente_id)


@router.get("/producoes/{producao_id}", response_model=ProducaoClienteResponse)
def obter_minha_producao(producao_id: int, db: Db, user: CurrentClient):
    try:
        return portal_cliente_service.buscar_producao(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None


@router.get(
    "/producoes/{producao_id}/financeiro",
    response_model=FinanceiroClienteResponse,
)
def obter_meu_financeiro(producao_id: int, db: Db, user: CurrentClient):
    try:
        return portal_cliente_service.buscar_financeiro(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None
    except financial_service.FinanceiroConflito:
        raise HTTPException(status_code=409, detail="Situacao financeira inconsistente.") from None
