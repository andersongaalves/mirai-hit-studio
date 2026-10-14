"""Catalog combos (Roadmap 3.0, 5.08), admin only."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from schemas.combo import ComboResponse, ComboWrite
from services import combo_service as service

router = APIRouter(prefix="/combos", tags=["Combos"], dependencies=[Depends(require_admin)])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]


def _error(exc):
    if isinstance(exc, service.ComboNaoEncontrado):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.get("", response_model=list[ComboResponse])
def listar(db: Db):
    return service.listar(db)


@router.post("", response_model=ComboResponse, status_code=201)
def criar(dados: ComboWrite, request: Request, db: Db, user=Depends(require_admin)):
    try:
        return service.criar(db, dados, actor=user, request_id=getattr(request.state, "request_id", None))
    except service.ComboError as exc:
        raise _error(exc) from None


@router.put("/{combo_id}", response_model=ComboResponse)
def atualizar(combo_id: IdPath, dados: ComboWrite, request: Request, db: Db, user=Depends(require_admin)):
    try:
        return service.atualizar(db, combo_id, dados, actor=user, request_id=getattr(request.state, "request_id", None))
    except service.ComboError as exc:
        raise _error(exc) from None
