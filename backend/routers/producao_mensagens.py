import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.dependencies import require_admin, require_client, require_producer
from core.rate_limit import allow_request
from database import get_db
from schemas.producao_mensagem import MensagemCreate, MensagemResponse
from services import producao_mensagem_service as service

router = APIRouter(tags=["Mensagens da producao"])
Db = Annotated[Session, Depends(get_db)]
MESSAGES_PER_MINUTE = 20


def _error(exc):
    if isinstance(exc, service.MensagemNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _rate_limit(user):
    try:
        allowed, retry = allow_request(f"production-message:{user.id}", MESSAGES_PER_MINUTE, 60)
    except (sqlite3.Error, OSError):
        raise HTTPException(status_code=503, detail="Protecao temporariamente indisponivel.") from None
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Muitas mensagens em pouco tempo. Aguarde para enviar novamente.",
            headers={"Retry-After": str(retry)},
        )


def _list(db, role, production_id, user):
    try:
        production = service.production_for(db, role, production_id, user)
        return service.list_messages(db, production, role=role, user=user)
    except service.MensagemError as exc:
        raise _error(exc) from None


def _post(db, role, production_id, user, payload: MensagemCreate):
    try:
        production = service.production_for(db, role, production_id, user)
        _rate_limit(user)
        return service.post_message(
            db, production, role=role, user=user, texto=payload.texto, audiencia=payload.audiencia,
            responde_a_id=payload.responde_a_id, arquivo_id=payload.arquivo_id,
        )
    except service.MensagemError as exc:
        raise _error(exc) from None


@router.get("/portal/cliente/producoes/{producao_id}/mensagens", response_model=list[MensagemResponse])
def client_messages(producao_id: int, db: Db, user=Depends(require_client)):
    return _list(db, "cliente", producao_id, user)


@router.post("/portal/cliente/producoes/{producao_id}/mensagens", response_model=MensagemResponse, status_code=201)
def client_post(producao_id: int, payload: MensagemCreate, db: Db, user=Depends(require_client)):
    return _post(db, "cliente", producao_id, user, payload)


@router.get("/portal/produtor/producoes/{producao_id}/mensagens", response_model=list[MensagemResponse])
def producer_messages(producao_id: int, db: Db, user=Depends(require_producer)):
    return _list(db, "produtor", producao_id, user)


@router.post("/portal/produtor/producoes/{producao_id}/mensagens", response_model=MensagemResponse, status_code=201)
def producer_post(producao_id: int, payload: MensagemCreate, db: Db, user=Depends(require_producer)):
    return _post(db, "produtor", producao_id, user, payload)


@router.get("/producoes/{producao_id}/mensagens", response_model=list[MensagemResponse])
def admin_messages(producao_id: int, db: Db, user=Depends(require_admin)):
    return _list(db, "admin", producao_id, user)


@router.post("/producoes/{producao_id}/mensagens", response_model=MensagemResponse, status_code=201)
def admin_post(producao_id: int, payload: MensagemCreate, db: Db, user=Depends(require_admin)):
    return _post(db, "admin", producao_id, user, payload)
