import json
import resend

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from database import SessionLocal, get_db
from integrations.mercado_pago import MercadoPagoClient, MercadoPagoError
from integrations.resend_ai_email import ResendAIEmailClient
from services.ai_conversation_service import ConversationService
from services.ai_email_service import AIEmailError, AIEmailService
from services.ai_email_channel import normalize_sender
from services.ai_openai_provider import OpenAIProvider
from services import mercado_pago_webhook_service as webhook_service


router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
MAX_WEBHOOK_BODY_BYTES = 64 * 1024
MAX_RESEND_BODY_BYTES = 256 * 1024


def get_mercado_pago_client() -> MercadoPagoClient:
    return MercadoPagoClient()


def _secret_value(value):
    return value.get_secret_value() if hasattr(value, "get_secret_value") else str(value or "")


def get_ai_email_service():
    api_key = getattr(settings, "AI_API_KEY", None)
    api_key = _secret_value(api_key)
    if (
        not getattr(settings, "AI_EMAIL_ENABLED", False)
        or not getattr(settings, "AI_ENABLED", False)
        or not api_key
        or not getattr(settings, "AI_MODEL", "")
        or not getattr(settings, "AI_EMAIL_FROM", "")
        or not normalize_sender(getattr(settings, "AI_EMAIL_INBOUND_ADDRESS", ""))
    ):
        raise HTTPException(status_code=503, detail="Canal de e-mail indisponivel.")
    try:
        client = ResendAIEmailClient(getattr(settings, "RESEND_API_KEY", ""))
        provider = OpenAIProvider(api_key, settings.AI_MODEL, timeout=settings.AI_TIMEOUT_SECONDS)
        return AIEmailService(
            ConversationService(SessionLocal, provider), client,
            sender_address=settings.AI_EMAIL_FROM,
            max_body_chars=getattr(settings, "AI_EMAIL_MAX_BODY_CHARS", 8000),
        )
    except AIEmailError:
        raise HTTPException(status_code=503, detail="Canal de e-mail indisponivel.") from None


def _verify_resend_signature(body, request):
    secret = _secret_value(getattr(settings, "RESEND_WEBHOOK_SECRET", ""))
    if not secret:
        raise HTTPException(status_code=503, detail="Webhook indisponivel.")
    try:
        payload = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Payload invalido.") from None
    headers = {
        "id": request.headers.get("svix-id", ""),
        "timestamp": request.headers.get("svix-timestamp", ""),
        "signature": request.headers.get("svix-signature", ""),
    }
    try:
        resend.Webhooks.verify({"payload": payload, "headers": headers, "webhook_secret": secret})
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Assinatura invalida.") from None


@router.post("/resend")
async def resend_webhook(request: Request, service=Depends(get_ai_email_service)):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_RESEND_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Webhook excede o limite permitido.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Requisicao invalida.") from None
    body = await request.body()
    if len(body) > MAX_RESEND_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook excede o limite permitido.")
    _verify_resend_signature(body, request)
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Payload invalido.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido.")
    try:
        outcome = service.handle(payload, request_id=request.headers.get("svix-id"))
    except AIEmailError as error:
        if str(error) in {"invalid_payload", "invalid_sender", "email_body_unavailable"}:
            raise HTTPException(status_code=400, detail="Payload invalido.") from None
        if str(error) in {"conversation_identity_mismatch", "conversation_closed"}:
            raise HTTPException(status_code=409, detail="Mensagem nao pode ser associada.") from None
        raise HTTPException(status_code=503, detail="Canal de e-mail temporariamente indisponivel.") from None
    return {"status": outcome.status, "duplicate": outcome.duplicate}


@router.post("/mercado-pago")
async def mercado_pago_webhook(
    request: Request,
    data_id: str | None = Query(default=None, alias="data.id"),
    event_type: str | None = Query(default=None, alias="type"),
    signature_header: str | None = Header(default=None, alias="x-signature"),
    provider_request_id: str | None = Header(default=None, alias="x-request-id"),
    db: Session = Depends(get_db),
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > MAX_WEBHOOK_BODY_BYTES:
                raise HTTPException(status_code=413, detail="Webhook excede o limite permitido.")
        except ValueError:
            raise HTTPException(status_code=400, detail="Requisicao invalida.") from None
    try:
        verified = webhook_service.verify_signature(
            signature_header,
            provider_request_id,
            data_id,
            settings.MERCADO_PAGO_WEBHOOK_SECRET,
        )
    except webhook_service.WebhookNotConfigured:
        raise HTTPException(status_code=503, detail="Webhook indisponivel.") from None
    except webhook_service.WebhookSignatureError:
        raise HTTPException(status_code=401, detail="Assinatura invalida.") from None

    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Webhook excede o limite permitido.")
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Payload invalido.") from None
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload invalido.")
    body_data = payload.get("data")
    body_resource_id = body_data.get("id") if isinstance(body_data, dict) else None
    body_type = payload.get("type")
    if body_resource_id is not None and str(body_resource_id) != data_id:
        raise HTTPException(status_code=400, detail="Identidade do webhook divergente.")
    if body_type is not None and str(body_type) != event_type:
        raise HTTPException(status_code=400, detail="Tipo do webhook divergente.")
    try:
        outcome = webhook_service.process_webhook(
            db,
            resource_id=data_id,
            event_type=event_type or "unknown",
            action=_safe_string(payload.get("action"), 100),
            provider_event_id=_safe_string(payload.get("id"), 200),
            provider_request_id=provider_request_id,
            signature_timestamp=verified.timestamp,
            client=client,
        )
    except MercadoPagoError:
        raise HTTPException(status_code=503, detail="Provider temporariamente indisponivel.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Persistencia temporariamente indisponivel.") from None
    return {
        "status": outcome.status,
        "duplicate": outcome.duplicate,
    }


def _safe_string(value, max_length: int) -> str | None:
    return str(value)[:max_length] if value is not None else None
