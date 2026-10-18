from typing import Annotated

from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from schemas.credito_alocacao import (
    AlocacaoResponse,
    ContextoCreditos,
    MovimentoCreditos,
    NovaProducaoCreditos,
    ReservaCreditos,
)
from services import credito_alocacao_service as service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/producoes", tags=["Alocacao de creditos"])
Db = Annotated[Session, Depends(get_db)]
Admin = Annotated[object, Depends(require_admin)]


def _executar(operation, *args, **kwargs):
    try:
        return operation(*args, **kwargs)
    except service.AlocacaoNaoEncontrada as error:
        raise HTTPException(404, str(error)) from None
    except service.AlocacaoInvalida as error:
        raise HTTPException(422, str(error)) from None
    except service.AlocacaoConflito as error:
        raise HTTPException(409, str(error)) from None


@router.get("/{producao_id}/creditos", response_model=list[AlocacaoResponse])
def listar(producao_id: int, response: Response, db: Db, user: Admin):
    response.headers["Cache-Control"] = "private, no-store"
    return _executar(service.listar, db, producao_id)


@router.get("/{producao_id}/creditos/contexto", response_model=ContextoCreditos)
def contexto(producao_id: int, response: Response, db: Db, user: Admin):
    response.headers["Cache-Control"] = "private, no-store"
    return _executar(service.contexto, db, producao_id)


@router.post("/creditos/cliente/{cliente_id}", response_model=AlocacaoResponse)
def criar_producao(cliente_id: int, dados: NovaProducaoCreditos, request: Request, db: Db, user: Admin):
    return _executar(service.criar_producao, db, cliente_id, dados, actor=user,
                     request_id=getattr(request.state, "request_id", None))


@router.post("/{producao_id}/creditos", response_model=AlocacaoResponse)
def reservar(producao_id: int, dados: ReservaCreditos, request: Request, db: Db, user: Admin):
    return _executar(service.reservar, db, producao_id, dados, actor=user,
                     request_id=getattr(request.state, "request_id", None))


@router.post("/{producao_id}/creditos/{alocacao_id}/movimentos", response_model=AlocacaoResponse)
def movimentar(producao_id: int, alocacao_id: int, dados: MovimentoCreditos, request: Request, db: Db, user: Admin):
    return _executar(service.movimentar, db, producao_id, alocacao_id, dados, actor=user,
                     request_id=getattr(request.state, "request_id", None))
