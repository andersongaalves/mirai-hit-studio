"""Authenticated operator endpoints for the unified AI Inbox."""

from fastapi import APIRouter, Depends, HTTPException, Query
from uuid import UUID
from datetime import datetime

from core.config import settings
from core.dependencies import require_ai_operator
from database import SessionLocal
from integrations.resend_ai_email import ResendAIEmailClient
from schemas.ai import Channel, ConversationMode, ConversationStatus
from schemas.ai_inbox import (
    InboxDetail, InboxMessageCreate, InboxMessageResponse, InboxModeUpdate,
    InboxMutationResponse, InboxPage, InboxSuggestionCreate,
    InboxSuggestionResponse,
)
from services.ai_conversation_service import ConversationService
from services.ai_email_service import AIEmailError, AIEmailService
from services.ai_inbox_service import AIInboxService, InboxError
from services.ai_openai_provider import OpenAIProvider


router = APIRouter(prefix="/admin/ai/conversations", tags=["AI Inbox"])


def _secret_value(value):
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value or "")


def get_ai_core():
    key = _secret_value(getattr(settings, "AI_API_KEY", ""))
    provider = None
    if getattr(settings, "AI_ENABLED", False) and key and getattr(settings, "AI_MODEL", ""):
        provider = OpenAIProvider(key, settings.AI_MODEL, timeout=settings.AI_TIMEOUT_SECONDS)
    return ConversationService(SessionLocal, provider)


def get_ai_email_delivery():
    if not getattr(settings, "AI_EMAIL_ENABLED", False):
        return None
    if not getattr(settings, "AI_EMAIL_FROM", "") or not getattr(settings, "RESEND_API_KEY", ""):
        return None
    try:
        return AIEmailService(
            ConversationService(SessionLocal),
            ResendAIEmailClient(settings.RESEND_API_KEY),
            sender_address=settings.AI_EMAIL_FROM,
            max_body_chars=getattr(settings, "AI_EMAIL_MAX_BODY_CHARS", 8000),
        )
    except AIEmailError:
        return None


def get_inbox_service(core=Depends(get_ai_core), email_delivery=Depends(get_ai_email_delivery)):
    return AIInboxService(SessionLocal, core, email_delivery)


def _error(error):
    code = str(error)
    status = {
        "conversation_not_found": 404,
        "message_not_found": 404,
        "suggestion_not_found": 404,
        "conversation_already_assigned": 409,
        "processing_conflict": 409,
        "stale_suggestion": 409,
        "conversation_closed": 409,
        "conversation_not_assigned": 403,
        "autonomous_mode_admin_locked": 409,
        "conversation_not_in_copilot": 409,
        "suggestion_unavailable": 503,
        "provider_unavailable": 503,
        "provider_timeout": 503,
        "provider_invalid_response": 503,
        "delivery_unavailable": 503,
        "idempotency_conflict": 409,
    }.get(code, 400)
    raise HTTPException(status_code=status, detail=code) from None


@router.get("", response_model=InboxPage)
def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    status: ConversationStatus | None = None,
    mode: ConversationMode | None = None,
    channel: Channel | None = None,
    handoff: bool = False,
    assigned_user_id: int | None = Query(None, gt=0),
    unassigned: bool = False,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    search: str | None = Query(None, max_length=80),
    service=Depends(get_inbox_service),
    _user=Depends(require_ai_operator),
):
    return service.list(
        page=page, page_size=page_size, status=status, mode=mode, channel=channel,
        handoff=handoff, assigned_user_id=assigned_user_id, search=search,
        unassigned=unassigned, updated_from=updated_from, updated_to=updated_to,
    )


@router.get("/{conversation_id}", response_model=InboxDetail)
def get_conversation(
    conversation_id: str,
    before: UUID | None = None,
    service=Depends(get_inbox_service),
    _user=Depends(require_ai_operator),
):
    try:
        return service.detail(conversation_id, before=before)
    except InboxError as error:
        _error(error)


@router.post("/{conversation_id}/assign", response_model=InboxMutationResponse)
def assign_conversation(
    conversation_id: str,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return {"conversation": service.assign(conversation_id, user)}
    except InboxError as error:
        _error(error)


@router.patch("/{conversation_id}/mode", response_model=InboxMutationResponse)
def set_conversation_mode(
    conversation_id: str,
    payload: InboxModeUpdate,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return {"conversation": service.set_mode(conversation_id, payload.mode, user)}
    except InboxError as error:
        _error(error)


@router.post("/{conversation_id}/suggestions", response_model=InboxSuggestionResponse)
def create_suggestion(
    conversation_id: str,
    payload: InboxSuggestionCreate | None = None,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        suggestion = service.suggest(conversation_id, user, payload.message_id if payload else None)
        return {"suggestion": suggestion}
    except InboxError as error:
        _error(error)


@router.post("/{conversation_id}/messages", response_model=InboxMessageResponse)
def send_message(
    conversation_id: str,
    payload: InboxMessageCreate,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return service.send_message(conversation_id, payload, user)
    except InboxError as error:
        _error(error)


@router.post("/{conversation_id}/close", response_model=InboxMutationResponse)
def close_conversation(
    conversation_id: str,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return {"conversation": service.close(conversation_id, user)}
    except InboxError as error:
        _error(error)


@router.delete("/{conversation_id}/suggestions/{suggestion_id}", response_model=InboxMutationResponse)
def ignore_suggestion(
    conversation_id: str,
    suggestion_id: UUID,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return {"conversation": service.ignore_suggestion(conversation_id, suggestion_id, user)}
    except InboxError as error:
        _error(error)


@router.post("/{conversation_id}/messages/{message_id}/retry", response_model=InboxMessageResponse)
def retry_message(
    conversation_id: str,
    message_id: UUID,
    service=Depends(get_inbox_service),
    user=Depends(require_ai_operator),
):
    try:
        return service.retry_message(conversation_id, message_id, user)
    except InboxError as error:
        _error(error)
