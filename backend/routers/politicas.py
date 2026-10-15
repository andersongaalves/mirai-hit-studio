"""Contractual portal policies (Roadmap 3.0, 5.10). Admin only; portals feel them via enforcement."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from schemas.politica import (
    ExcecaoPoliticas,
    PoliticasGlobaisPublicar,
    PoliticasGlobaisResponse,
    PoliticasGlobaisRestaurar,
    PoliticasParciais,
    PoliticasProducaoResponse,
    PoliticasServicoResponse,
)
from services import politica_service as service
from services import producao_etapa_service as producoes

router = APIRouter(tags=["Politicas dos portais"])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]


def _request_id(request: Request):
    return getattr(request.state, "request_id", None)


def _error(exc):
    if isinstance(exc, service.PoliticaNaoEncontrada):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.PoliticaConflito):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, (service.PoliticaInvalida, ValidationError)):
        return HTTPException(status_code=422, detail="Politicas invalidas.")
    return exc


def _globais(db):
    return {**service.globais(db), "padroes": service.padroes(), "versoes": service.versoes(db)}


@router.get("/politicas/globais", response_model=PoliticasGlobaisResponse)
def global_policies(db: Db, user=Depends(require_admin)):
    return _globais(db)


@router.put("/politicas/globais", response_model=PoliticasGlobaisResponse)
def publish_global_policies(dados: PoliticasGlobaisPublicar, request: Request, db: Db, user=Depends(require_admin)):
    try:
        service.publicar_globais(db, dados.politicas.model_dump(), actor=user, base_versao=dados.base_versao,
                                 request_id=_request_id(request))
    except service.PoliticaError as exc:
        raise _error(exc) from None
    return _globais(db)


@router.post("/politicas/globais/restaurar", response_model=PoliticasGlobaisResponse)
def restore_global_policies(dados: PoliticasGlobaisRestaurar, request: Request, db: Db, user=Depends(require_admin)):
    try:
        service.restaurar_globais(db, dados.versao, actor=user, base_versao=dados.base_versao,
                                  request_id=_request_id(request))
    except service.PoliticaError as exc:
        raise _error(exc) from None
    return _globais(db)


@router.get("/servicos/{servico_id}/politicas", response_model=PoliticasServicoResponse)
def service_policies(servico_id: IdPath, db: Db, user=Depends(require_admin)):
    try:
        politicas = service.politicas_servico(db, servico_id)
    except service.PoliticaError as exc:
        raise _error(exc) from None
    return {"servico_id": servico_id, "politicas": politicas, "herdadas": service.globais(db)["politicas"]}


@router.put("/servicos/{servico_id}/politicas", response_model=PoliticasServicoResponse)
def save_service_policies(servico_id: IdPath, dados: PoliticasParciais, request: Request, db: Db,
                          user=Depends(require_admin)):
    try:
        politicas = service.salvar_servico(db, servico_id, dados.model_dump(exclude_none=True), actor=user,
                                           request_id=_request_id(request))
    except service.PoliticaError as exc:
        raise _error(exc) from None
    return {"servico_id": servico_id, "politicas": politicas, "herdadas": service.globais(db)["politicas"]}


def _producao(db, producao_id, user):
    try:
        return producoes.producao_para(db, "admin", producao_id, user)
    except producoes.EtapaError:
        raise HTTPException(status_code=404, detail="Producao nao encontrada.") from None


@router.get("/producoes/{producao_id}/politicas", response_model=PoliticasProducaoResponse)
def production_policies(producao_id: IdPath, db: Db, user=Depends(require_admin)):
    return service.detalhar(db, _producao(db, producao_id, user).id)


@router.put("/producoes/{producao_id}/politicas", response_model=PoliticasProducaoResponse)
def set_production_exception(producao_id: IdPath, dados: ExcecaoPoliticas, request: Request, db: Db,
                             user=Depends(require_admin)):
    producao = _producao(db, producao_id, user)
    try:
        return service.definir_excecao(db, producao, dados.politicas.model_dump(exclude_none=True), dados.motivo,
                                       actor=user, request_id=_request_id(request))
    except service.PoliticaError as exc:
        raise _error(exc) from None


@router.delete("/producoes/{producao_id}/politicas", response_model=PoliticasProducaoResponse)
def remove_production_exception(producao_id: IdPath, request: Request, db: Db, user=Depends(require_admin)):
    producao = _producao(db, producao_id, user)
    try:
        return service.remover_excecao(db, producao, actor=user, request_id=_request_id(request))
    except service.PoliticaError as exc:
        raise _error(exc) from None
