"""Contract stages of a production (Roadmap 3.0, 5.06)."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.orm import Session

from core.dependencies import require_admin, require_client, require_producer
from database import get_db
from schemas.producao_etapa import EtapaAdminUpdate, EtapasProducaoResponse, EtapaStatusUpdate
from services import producao_etapa_service as service

router = APIRouter(tags=["Etapas da producao"])
Db = Annotated[Session, Depends(get_db)]
IdPath = Annotated[int, Path(gt=0)]


def _error(exc):
    if isinstance(exc, service.EtapaNaoEncontrada):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, service.EtapaConflito):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _request_id(request: Request):
    return getattr(request.state, "request_id", None)


def _list(db, papel, producao_id, user):
    try:
        producao = service.producao_para(db, papel, producao_id, user)
        return service.listar(db, producao, papel=papel, usuario=user)
    except service.EtapaError as exc:
        raise _error(exc) from None


@router.get("/portal/cliente/producoes/{producao_id}/etapas", response_model=EtapasProducaoResponse,
            response_model_exclude_none=True)
def client_stages(producao_id: IdPath, db: Db, user=Depends(require_client)):
    return _list(db, "cliente", producao_id, user)


@router.get("/portal/produtor/producoes/{producao_id}/etapas", response_model=EtapasProducaoResponse,
            response_model_exclude_none=True)
def producer_stages(producao_id: IdPath, db: Db, user=Depends(require_producer)):
    return _list(db, "produtor", producao_id, user)


@router.patch("/portal/produtor/producoes/{producao_id}/etapas/{etapa_id}", response_model=EtapasProducaoResponse,
              response_model_exclude_none=True)
def producer_update_stage(producao_id: IdPath, etapa_id: IdPath, dados: EtapaStatusUpdate, request: Request,
                          db: Db, user=Depends(require_producer)):
    try:
        producao = service.producao_para(db, "produtor", producao_id, user)
        return service.atualizar(db, producao, etapa_id, papel="produtor", usuario=user, status=dados.status,
                                 status_atual=dados.status_atual, request_id=_request_id(request))
    except service.EtapaError as exc:
        raise _error(exc) from None


@router.get("/producoes/{producao_id}/etapas-contratuais", response_model=EtapasProducaoResponse)
def admin_stages(producao_id: IdPath, db: Db, user=Depends(require_admin)):
    return _list(db, "admin", producao_id, user)


@router.post("/producoes/{producao_id}/etapas-contratuais/gerar", response_model=EtapasProducaoResponse)
def admin_generate_stages(producao_id: IdPath, request: Request, db: Db, user=Depends(require_admin)):
    try:
        return service.gerar(db, producao_id, actor=user, request_id=_request_id(request))
    except service.EtapaError as exc:
        raise _error(exc) from None


@router.patch("/producoes/{producao_id}/etapas-contratuais/{etapa_id}", response_model=EtapasProducaoResponse)
def admin_update_stage(producao_id: IdPath, etapa_id: IdPath, dados: EtapaAdminUpdate, request: Request,
                       db: Db, user=Depends(require_admin)):
    if dados.status is not None and dados.status_atual is None:
        raise HTTPException(status_code=422, detail="Informe o status atual da etapa.")
    if dados.status is None and "prazo" not in dados.model_fields_set:
        raise HTTPException(status_code=422, detail="Nada para atualizar.")
    try:
        producao = service.producao_para(db, "admin", producao_id, user)
        return service.atualizar(
            db, producao, etapa_id, papel="admin", usuario=user, status=dados.status,
            status_atual=dados.status_atual, prazo=dados.prazo, alterar_prazo="prazo" in dados.model_fields_set,
            request_id=_request_id(request),
        )
    except service.EtapaError as exc:
        raise _error(exc) from None
