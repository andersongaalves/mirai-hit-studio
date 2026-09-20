import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from database import get_db
from integrations.mercado_pago import MercadoPagoClient, MercadoPagoError
from services import mercado_pago_webhook_service as webhook_service


router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
MAX_WEBHOOK_BODY_BYTES = 64 * 1024


def get_mercado_pago_client() -> MercadoPagoClient:
    return MercadoPagoClient()


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
