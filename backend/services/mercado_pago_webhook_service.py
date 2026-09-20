import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from integrations.mercado_pago import MercadoPagoClient, MercadoPagoError
from models.financeiro import ProviderWebhookEventModel
from services import mercado_pago_service


SIGNATURE_PART_PATTERN = re.compile(r"^[0-9a-f]{64}$")
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
TERMINAL_EVENT_STATUSES = {"processed", "ignored", "conflict"}


class WebhookSignatureError(Exception):
    pass


class WebhookNotConfigured(Exception):
    pass


@dataclass(frozen=True)
class WebhookSignature:
    timestamp: str


@dataclass(frozen=True)
class WebhookOutcome:
    status: str
    duplicate: bool = False
    payment_id: int | None = None


def verify_signature(
    signature_header: str | None,
    request_id: str | None,
    resource_id: str | None,
    secret: str | None,
) -> WebhookSignature:
    if not isinstance(secret, str) or not secret:
        raise WebhookNotConfigured()
    if (
        not isinstance(signature_header, str)
        or not isinstance(request_id, str)
        or not REQUEST_ID_PATTERN.fullmatch(request_id)
        or not isinstance(resource_id, str)
        or not 1 <= len(resource_id) <= 200
    ):
        raise WebhookSignatureError()
    parts: dict[str, list[str]] = {}
    for raw_part in signature_header.split(","):
        key, separator, value = raw_part.strip().partition("=")
        if separator and key and value:
            parts.setdefault(key, []).append(value)
    timestamps = parts.get("ts", [])
    digests = parts.get("v1", [])
    if len(timestamps) != 1 or not timestamps[0].isdigit() or not digests:
        raise WebhookSignatureError()
    if any(not SIGNATURE_PART_PATTERN.fullmatch(value) for value in digests):
        raise WebhookSignatureError()
    manifest = (
        f"id:{resource_id.lower()};request-id:{request_id};ts:{timestamps[0]};"
    )
    expected = hmac.new(
        secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if not any(hmac.compare_digest(expected, value) for value in digests):
        raise WebhookSignatureError()
    return WebhookSignature(timestamp=timestamps[0])


def process_webhook(
    db: Session,
    *,
    resource_id: str,
    event_type: str,
    action: str | None,
    provider_event_id: str | None,
    provider_request_id: str,
    signature_timestamp: str,
    client: MercadoPagoClient,
) -> WebhookOutcome:
    deduplication_key = _deduplication_key(
        resource_id, provider_request_id, signature_timestamp
    )
    event, duplicate = _register_event(
        db,
        resource_id=resource_id,
        event_type=event_type,
        action=action,
        provider_event_id=provider_event_id,
        provider_request_id=provider_request_id,
        deduplication_key=deduplication_key,
    )
    if duplicate and event.status in TERMINAL_EVENT_STATUSES:
        return WebhookOutcome(event.status, duplicate=True, payment_id=event.pagamento_id)
    if event_type != "order":
        _finish_event(db, event.id, "ignored")
        return WebhookOutcome("ignored", duplicate=duplicate)
    try:
        result = mercado_pago_service.reconcile_order(
            db,
            resource_id,
            client=client,
            request_id=provider_request_id,
        )
    except mercado_pago_service.ReconciliationConflict as error:
        _finish_event(
            db,
            event.id,
            "conflict",
            payment_id=error.payment_id,
            error_category=error.reason,
        )
        return WebhookOutcome("conflict", duplicate=duplicate, payment_id=error.payment_id)
    except MercadoPagoError as error:
        _finish_event(db, event.id, "failed", error_category=error.code)
        raise
    _finish_event(db, event.id, "processed", payment_id=result.payment_id)
    return WebhookOutcome("processed", duplicate=duplicate, payment_id=result.payment_id)


def _deduplication_key(
    resource_id: str, provider_request_id: str, signature_timestamp: str
) -> str:
    safe_identity = (
        f"mercado_pago\n{resource_id.lower()}\n{provider_request_id}\n"
        f"{signature_timestamp}"
    )
    return hashlib.sha256(safe_identity.encode("utf-8")).hexdigest()


def _register_event(
    db: Session,
    *,
    resource_id: str,
    event_type: str,
    action: str | None,
    provider_event_id: str | None,
    provider_request_id: str,
    deduplication_key: str,
) -> tuple[ProviderWebhookEventModel, bool]:
    event = ProviderWebhookEventModel(
        provider="mercado_pago",
        resource_id=resource_id,
        event_type=event_type[:50],
        action=action[:100] if action else None,
        provider_event_id=provider_event_id[:200] if provider_event_id else None,
        provider_request_id=provider_request_id,
        deduplication_key=deduplication_key,
        status="received",
    )
    db.add(event)
    try:
        db.commit()
        db.refresh(event)
        return event, False
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ProviderWebhookEventModel).where(
                ProviderWebhookEventModel.deduplication_key == deduplication_key
            )
        )
        if existing is None:
            raise
        return existing, True


def _finish_event(
    db: Session,
    event_id: int,
    status: str,
    *,
    payment_id: int | None = None,
    error_category: str | None = None,
) -> None:
    event = db.scalar(
        select(ProviderWebhookEventModel)
        .where(ProviderWebhookEventModel.id == event_id)
        .with_for_update()
    )
    if event is None:
        db.rollback()
        raise RuntimeError("webhook_event_not_found")
    event.status = status
    event.pagamento_id = payment_id
    event.error_category = error_category[:64] if error_category else None
    event.processed_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
