"""Public, unverified site channel. Bearer tokens here are NOT administrative JWTs."""
import sqlite3

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response

from core.config import settings
from core.rate_limit import allow_request
from database import SessionLocal
from schemas.ai_site import SiteHistory, SiteMessage, SiteReply, SiteSession
from services.ai_conversation_service import ConversationError, ConversationService
from services.ai_openai_provider import OpenAIProvider
from services.ai_site_service import SiteChatService, token_reference


def limit(identity, count, window):
    try:
        allowed, wait = allow_request("ai-chat:" + identity, count, window)
    except (sqlite3.Error, OSError):
        raise HTTPException(503, "Chat temporariamente indisponivel.") from None
    if not allowed:
        raise HTTPException(429, "Aguarde antes de tentar novamente.", headers={"Retry-After": str(wait)})


def public_access(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    ip = request.client.host if request.client else "unknown"
    limit("ip:" + ip, 60, 60)
    if request.url.path.endswith("/session"):
        limit("new:" + ip, 10, 3600)


def session_token(authorization: str = Header(default="")):
    token = authorization.removeprefix("Bearer ") if authorization.startswith("Bearer ") else ""
    try:
        reference = token_reference(token)
    except ConversationError:
        raise HTTPException(401, "Sessao invalida ou expirada.") from None
    limit("session:" + reference, 20, 60)
    return token


def get_site_chat_service():
    key = getattr(settings, "AI_API_KEY", None)
    key = key.get_secret_value() if key else ""
    enabled = bool(getattr(settings, "AI_ENABLED", False) and key and getattr(settings, "AI_MODEL", ""))
    provider = OpenAIProvider(key, settings.AI_MODEL, timeout=settings.AI_TIMEOUT_SECONDS,
                             max_output_tokens=getattr(settings, "AI_MAX_OUTPUT_TOKENS", 1200)) if enabled else None
    service = SiteChatService(ConversationService(SessionLocal, provider), session_hours=getattr(settings, "AI_SESSION_HOURS", 24))
    service.ai_enabled = enabled
    return service


def run(action):
    try:
        return action()
    except ConversationError as error:
        code = str(error)
        if code == "invalid_session":
            raise HTTPException(401, "Sessao invalida ou expirada.") from None
        if code in {"conversation_closed", "processing_conflict", "idempotency_conflict"}:
            raise HTTPException(409, "Conversa encerrada ou mensagem em processamento.") from None
        raise HTTPException(503, "Nao foi possivel responder agora.") from None


router = APIRouter(prefix="/ai/chat", tags=["Site chat"], dependencies=[Depends(public_access)])


@router.post("/session", response_model=SiteSession, status_code=201)
def create_session(service=Depends(get_site_chat_service)):
    if not getattr(service, "ai_enabled", True):
        raise HTTPException(503, "Chat temporariamente indisponivel.")
    return run(service.create_session)


@router.get("/history", response_model=SiteHistory)
def history(token=Depends(session_token), service=Depends(get_site_chat_service)):
    return run(lambda: service.history(token))


@router.post("/messages", response_model=SiteReply)
def message(payload: SiteMessage, token=Depends(session_token), service=Depends(get_site_chat_service)):
    return run(lambda: service.message(token, payload))
