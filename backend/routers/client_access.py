from core.dependencies import require_admin
from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Request
from schemas.client_access import (
    ClientAccessStatus,
    ClientInviteActivation,
    ClientInviteActivationResult,
    ClientInviteToken,
    ClientInviteValidation,
)
from services import client_access_service as service
from sqlalchemy.orm import Session

router = APIRouter(tags=["Acesso de clientes"])


def _source(request: Request):
    return request.client.host if request.client else "unknown"


def _error(error):
    if isinstance(error, service.ClientAccessNotFound):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, service.ClientAccessInvalid):
        raise HTTPException(status_code=422, detail=str(error)) from None
    if isinstance(error, service.ClientAccessConflict):
        raise HTTPException(status_code=409, detail=str(error)) from None
    if isinstance(error, service.ClientAccessRateLimited):
        raise HTTPException(status_code=429, detail=str(error)) from None
    if isinstance(error, service.ClientAccessDeliveryUnavailable):
        raise HTTPException(status_code=503, detail=str(error)) from None
    raise error


@router.get("/propostas/{proposta_id}/acesso-cliente", response_model=ClientAccessStatus)
def access_status(
    proposta_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return service.status(db, proposta_id)
    except service.ClientAccessError as error:
        _error(error)


@router.post("/propostas/{proposta_id}/acesso-cliente/convidar", response_model=ClientAccessStatus)
def invite(
    proposta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return service.invite(
            db,
            proposta_id,
            user,
            getattr(request.state, "request_id", None),
            _source(request),
        )
    except service.ClientAccessError as error:
        _error(error)


@router.post("/propostas/{proposta_id}/acesso-cliente/reenviar", response_model=ClientAccessStatus)
def resend(
    proposta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return service.resend(
            db,
            proposta_id,
            user,
            getattr(request.state, "request_id", None),
            _source(request),
        )
    except service.ClientAccessError as error:
        _error(error)


@router.post("/propostas/{proposta_id}/acesso-cliente/revogar", response_model=ClientAccessStatus)
def revoke(
    proposta_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return service.revoke(
            db,
            proposta_id,
            user,
            getattr(request.state, "request_id", None),
        )
    except service.ClientAccessError as error:
        _error(error)


@router.post("/cliente-acessos/validar", response_model=ClientInviteValidation)
def validate_invite(data: ClientInviteToken, request: Request, db: Session = Depends(get_db)):
    try:
        return {"estado": service.token_state(db, data.token, _source(request))}
    except service.ClientAccessError as error:
        _error(error)


@router.post("/cliente-acessos/ativar", response_model=ClientInviteActivationResult)
def activate_invite(
    data: ClientInviteActivation,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        service.activate(
            db,
            data,
            _source(request),
            getattr(request.state, "request_id", None),
        )
        return {"activated": True, "login_url": "/acesso"}
    except service.ClientAccessError as error:
        _error(error)
