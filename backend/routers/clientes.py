from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.dependencies import get_current_user
from database import get_db
from schemas.cliente import ClienteCreate, ClienteDetail, ClienteResponse, ClienteSummary, ClienteUpdate
from services import cliente_service


router = APIRouter(prefix="/clientes", tags=["Clientes"])


def _erro(error):
    if isinstance(error, cliente_service.ClienteNaoEncontrado):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, cliente_service.ClienteConflito):
        raise HTTPException(status_code=409, detail=str(error)) from None
    if isinstance(error, cliente_service.ClienteInvalido):
        raise HTTPException(status_code=422, detail=str(error)) from None
    raise error


@router.get("", response_model=list[ClienteSummary])
def listar_clientes(
    busca: str = Query(default="", max_length=150),
    ativo: bool | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return cliente_service.listar(db, busca.strip(), ativo)


@router.get("/{cliente_id}", response_model=ClienteDetail)
def obter_cliente(
    cliente_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return cliente_service.buscar(db, cliente_id)
    except Exception as error:
        _erro(error)


@router.post("", response_model=ClienteResponse, status_code=201)
def criar_cliente(
    dados: ClienteCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return cliente_service.criar(db, dados)
    except Exception as error:
        _erro(error)


@router.patch("/{cliente_id}", response_model=ClienteResponse)
def atualizar_cliente(
    cliente_id: int,
    dados: ClienteUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    try:
        return cliente_service.atualizar(db, cliente_id, dados)
    except Exception as error:
        _erro(error)
