"""Before/after comparison: chosen by the Admin, played at matched loudness (Roadmap 3.0)."""
from typing import Annotated

from core.dependencies import require_admin, require_client
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from models import ProducaoModel
from pydantic import BaseModel, ConfigDict, Field
from services import (
    comparativo_service,
    portal_cliente_service,
    producao_arquivo_service,
)
from sqlalchemy.orm import Session

router = APIRouter(tags=["Comparativo antes e depois"])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]
FileQuery = Annotated[int | None, Query(gt=0)]


class ComparativoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    antes_arquivo_id: int | None = Field(default=None, gt=0)
    depois_arquivo_id: int | None = Field(default=None, gt=0)


class ComparativoResponse(BaseModel):
    origem: str
    antes_arquivo_id: int | None
    depois_arquivo_id: int | None
    lufs_antes: float | None
    lufs_depois: float | None
    ganho_antes_db: float | None


def _production(db, producao_id):
    production = db.get(ProducaoModel, producao_id)
    if production is None:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.")
    return production


def _pair(db, production, antes, depois):
    try:
        return (comparativo_service._file_of(db, production, antes) if antes else None,
                comparativo_service._file_of(db, production, depois) if depois else None)
    except comparativo_service.ComparativoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


@router.get("/producoes/{producao_id}/comparativo", response_model=ComparativoResponse)
def admin_comparison(producao_id: IdPath, db: Db, antes: FileQuery = None, depois: FileQuery = None,
                     user=Depends(require_admin)):
    production = _production(db, producao_id)
    first, second = _pair(db, production, antes, depois)
    return comparativo_service.resposta(db, production, antes=first, depois=second)


@router.put("/producoes/{producao_id}/comparativo", response_model=ComparativoResponse)
def admin_set_comparison(producao_id: IdPath, dados: ComparativoUpdate, request: Request, db: Db,
                         user=Depends(require_admin)):
    production = _production(db, producao_id)
    try:
        comparativo_service.definir(db, production, user, antes_id=dados.antes_arquivo_id,
                                    depois_id=dados.depois_arquivo_id,
                                    request_id=getattr(request.state, "request_id", None))
    except comparativo_service.ComparativoError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return comparativo_service.resposta(db, production)


@router.get("/portal/cliente/producoes/{producao_id}/comparativo", response_model=ComparativoResponse)
def client_comparison(producao_id: IdPath, db: Db, antes: FileQuery = None, depois: FileQuery = None,
                      user=Depends(require_client)):
    try:
        production = portal_cliente_service.buscar_producao(db, producao_id, user.cliente_id)
    except portal_cliente_service.ProducaoClienteNaoEncontrada:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None

    def visible(file_id):
        if file_id is None:
            return None
        try:
            model = producao_arquivo_service.get_for_client(db, file_id, user.cliente_id)
        except producao_arquivo_service.ProducaoArquivoError:
            return None
        return model if model.producao_id == production.id else None

    # A manual choice only reaches the client when both files are visible to them.
    return comparativo_service.resposta(db, production, antes=visible(antes), depois=visible(depois),
                                        permitido=lambda model: visible(model.id) is not None)
