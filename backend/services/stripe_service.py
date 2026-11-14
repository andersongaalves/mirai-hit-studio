"""Mirai Hit Labs international purchases with Stripe Checkout (English store, USD).

The price in dollars is the same number as the plugin price (R$ 149,90 -> US$ 149.90):
the studio sets one price and the store shows it in the visitor's currency.

Flow: the buyer opens an order -> the license is reserved -> Stripe Checkout (hosted page)
-> Stripe confirms (webhook ``checkout.session.completed`` or the buyer's return, which asks
Stripe directly) -> the license becomes active. Refunds and disputes suspend it.
Stripe is called through its REST API with httpx; webhook signatures are checked here.
"""
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal

import httpx
from core import config
from fastapi import HTTPException
from models import PluginLicencaModel, PluginPedidoStripeModel
from services import audit_service, plugin_service
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

API = "https://api.stripe.com/v1"
TIMEOUT = 15.0
SIGNATURE_TOLERANCE = 300  # seconds
UNAVAILABLE = "International payment is unavailable right now. Try again in a few minutes."


def _secret(name):
    value = getattr(config.settings, name, "")
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return (value or "").strip()


def configurado() -> bool:
    return bool(_secret("STRIPE_SECRET_KEY"))


def _labs_url():
    return (getattr(config.settings, "LABS_PUBLIC_URL", "") or "https://labs.miraihitstudio.com.br").rstrip("/")


def _now():
    return datetime.now(timezone.utc)


def _api(method: str, path: str, data=None, idempotency_key=None):
    """One Stripe request. Raises HTTPException(503) on any failure (details stay in our logs)."""
    headers = {"Authorization": f"Bearer {_secret('STRIPE_SECRET_KEY')}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    try:
        response = httpx.request(method, f"{API}{path}", data=data, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError:
        logger.error("stripe_request_failed path=%s", path.split("/")[1] if "/" in path else path)
        raise HTTPException(503, UNAVAILABLE) from None
    if response.status_code >= 400:
        try:
            code = (response.json().get("error") or {}).get("code") or "unknown"
        except ValueError:
            code = "unknown"
        logger.error("stripe_request_rejected status=%s code=%s", response.status_code, code)
        raise HTTPException(503, UNAVAILABLE)
    return response.json()


def _cents(value) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1")))


def _fingerprint(user_id, plugin_id, price):
    return hashlib.sha256(json.dumps({"user": user_id, "plugin": plugin_id, "price": str(price), "currency": "usd"},
                                     sort_keys=True).encode()).hexdigest()


def _open_order_response(order):
    return {"pedido_id": order.id, "checkout_url": order.checkout_url}


def _still_open(order):
    expires = order.expira_em
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return order.status == "aberto" and order.checkout_url and (expires is None or expires > _now())


# ---------------------------------------------------------------- buying


def criar_checkout(db: Session, slug: str, actor, idempotency_key: str, request_id=None):
    if not configurado():
        raise HTTPException(503, UNAVAILABLE)
    plugin = plugin_service._publicado(db, slug)
    if not plugin.arquivos:
        raise HTTPException(409, "This plugin isn't available yet.")
    price = plugin_service.preco_vigente(plugin)
    if price <= 0:
        raise HTTPException(409, "This plugin is free: get it without checkout.")
    client = actor.cliente
    if client is None or not client.ativo or not client.email:
        raise HTTPException(409, "Complete seu cadastro antes de comprar.")
    if plugin_service._licenca_ativa(db, plugin.id, client.id) is not None:
        raise HTTPException(409, "Você já tem este plugin. Baixe em Meus plugins.")
    fingerprint = _fingerprint(actor.id, plugin.id, price)

    existing = db.scalar(select(PluginPedidoStripeModel).where(PluginPedidoStripeModel.idempotency_key == idempotency_key))
    if existing is not None:
        if existing.request_hash != fingerprint:
            raise HTTPException(409, "Chave de repetição usada para outra compra.")
        if _still_open(existing):
            return _open_order_response(existing)
    # Coming back before paying reopens the same Stripe page instead of a new order.
    pending = db.scalars(select(PluginPedidoStripeModel).where(
        PluginPedidoStripeModel.usuario_id == actor.id, PluginPedidoStripeModel.plugin_id == plugin.id,
        PluginPedidoStripeModel.status == "aberto", PluginPedidoStripeModel.valor == price,
    ).order_by(PluginPedidoStripeModel.id.desc())).first()
    if pending is not None and _still_open(pending):
        return _open_order_response(pending)
    if existing is not None:
        raise HTTPException(409, "Esta tentativa de compra expirou; recarregue a página.")

    license = plugin_service._conceder(db, plugin, client.id, "stripe", valor=price, status="reservada")
    order = PluginPedidoStripeModel(
        plugin_id=plugin.id, cliente_id=client.id, usuario_id=actor.id, licenca_id=license.id, valor=price,
        moeda="usd", status="aberto", idempotency_key=idempotency_key, request_hash=fingerprint,
    )
    db.add(order)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Compra concorrente; recarregue a página.") from None
    audit_service.record(db, actor=actor, action="plugin.stripe_order_opened", entity_type="plugin_pedido_stripe",
                         entity_id=order.id, metadata={"plugin_id": plugin.id, "licenca_id": license.id},
                         request_id=request_id)
    db.commit()

    base = _labs_url()
    try:
        session = _api("POST", "/checkout/sessions", data={
            "mode": "payment",
            "locale": "en",
            "client_reference_id": str(order.id),
            "customer_email": client.email,
            "line_items[0][quantity]": "1",
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(_cents(price)),
            "line_items[0][price_data][product_data][name]": plugin.nome,
            "line_items[0][price_data][product_data][description]": "Mirai Hit Labs plugin - personal license",
            "metadata[order_id]": str(order.id),
            "payment_intent_data[metadata][order_id]": str(order.id),
            "success_url": f"{base}/my-plugins?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{base}/plugins/{plugin.slug}?checkout=cancelled",
        }, idempotency_key=f"mirai-labs-order-{order.id}")
    except HTTPException:
        _encerrar(db, order, "expirado", None)
        db.commit()
        raise
    url = session.get("url")
    if not isinstance(url, str) or not url.startswith("https://checkout.stripe.com/") or not session.get("id"):
        logger.error("stripe_session_unexpected order_id=%s", order.id)
        _encerrar(db, order, "expirado", None)
        db.commit()
        raise HTTPException(503, UNAVAILABLE)
    order.stripe_session_id = str(session["id"])
    order.checkout_url = url
    if isinstance(session.get("expires_at"), int):
        order.expira_em = datetime.fromtimestamp(session["expires_at"], tz=timezone.utc)
    db.commit()
    return _open_order_response(order)


# ---------------------------------------------------------------- state changes


def _pagar(db, order, payment_intent, request_id=None):
    if order.status == "pago":
        return
    if order.status != "aberto":
        # Paid after we gave up on it (late payment): still the buyer's money -> activate.
        logger.warning("stripe_late_payment order_id=%s status=%s", order.id, order.status)
    license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.id == order.licenca_id).with_for_update())
    order.status = "pago"
    order.pago_em = _now()
    if payment_intent:
        order.stripe_payment_intent = str(payment_intent)
    if license is not None and license.status in ("reservada", "cancelada"):
        license.status = "ativa"
        license.ativada_em = _now()
        license.encerrada_em = None
        license.motivo = None
    audit_service.record(db, actor=None, action="plugin.license_activated", entity_type="plugin_licenca",
                         entity_id=order.licenca_id, metadata={"plugin_id": order.plugin_id, "stripe_order_id": order.id},
                         request_id=request_id)


def _encerrar(db, order, status, request_id=None):
    """Expired before paying: the reserved license is released."""
    if order.status != "aberto":
        return
    order.status = status
    license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.id == order.licenca_id).with_for_update())
    if license is not None and license.status == "reservada":
        license.status = "cancelada"
        license.encerrada_em = _now()
        license.motivo = "checkout_expirado"


def _reverter(db, order, status, request_id=None):
    """Refund or dispute: the license is suspended (shown as such in My plugins)."""
    if order.status not in ("pago", "reembolsado", "contestado"):
        return
    order.status = status
    license = db.scalar(select(PluginLicencaModel).where(PluginLicencaModel.id == order.licenca_id).with_for_update())
    if license is not None and license.status == "ativa":
        license.status = "reservada"
        license.encerrada_em = _now()
        license.motivo = "pagamento_revertido"
        audit_service.record(db, actor=None, action="plugin.license_suspended", entity_type="plugin_licenca",
                             entity_id=license.id, metadata={"plugin_id": order.plugin_id, "stripe_order_id": order.id},
                             request_id=request_id)


def _order_for_session(db, session):
    order_id = (session.get("metadata") or {}).get("order_id") or session.get("client_reference_id")
    order = None
    if session.get("id"):
        order = db.scalar(select(PluginPedidoStripeModel).where(
            PluginPedidoStripeModel.stripe_session_id == str(session["id"])).with_for_update())
    if order is None and str(order_id or "").isdigit():
        order = db.scalar(select(PluginPedidoStripeModel).where(
            PluginPedidoStripeModel.id == int(order_id)).with_for_update())
    return order


def _apply_session(db, session, request_id=None):
    order = _order_for_session(db, session)
    if order is None:
        return None
    if session.get("payment_status") in ("paid", "no_payment_required") and session.get("status") == "complete":
        if session.get("currency") not in (None, "usd") or (
                session.get("amount_total") is not None and int(session["amount_total"]) != _cents(order.valor)):
            logger.error("stripe_amount_mismatch order_id=%s", order.id)
            return order
        _pagar(db, order, session.get("payment_intent"), request_id)
    elif session.get("status") == "expired":
        _encerrar(db, order, "expirado", request_id)
    return order


# ---------------------------------------------------------------- webhook


def verificar_assinatura(payload: bytes, header: str | None, secret: str, now=None):
    """Stripe-Signature: t=<unix>,v1=<hex HMAC-SHA256 of "t.payload">."""
    if not secret or not header:
        return False
    parts = {}
    for item in header.split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        stamp = int(parts.get("t", [""])[0])
    except ValueError:
        return False
    if abs((now or time.time()) - stamp) > SIGNATURE_TOLERANCE:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in parts.get("v1", []))


def webhook(db: Session, payload: bytes, signature: str | None, request_id=None):
    if not verificar_assinatura(payload, signature, _secret("STRIPE_WEBHOOK_SECRET")):
        raise HTTPException(400, "Assinatura inválida.")
    try:
        event = json.loads(payload)
    except ValueError:
        raise HTTPException(400, "Evento inválido.") from None
    kind = event.get("type")
    obj = (event.get("data") or {}).get("object") or {}
    if kind in ("checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.expired"):
        _apply_session(db, obj, request_id)
    elif kind == "checkout.session.async_payment_failed":
        order = _order_for_session(db, obj)
        if order is not None:
            _encerrar(db, order, "expirado", request_id)
    elif kind in ("charge.refunded", "charge.dispute.created"):
        intent = obj.get("payment_intent")
        if intent:
            order = db.scalar(select(PluginPedidoStripeModel).where(
                PluginPedidoStripeModel.stripe_payment_intent == str(intent)).with_for_update())
            if order is not None:
                if kind == "charge.dispute.created":
                    _reverter(db, order, "contestado", request_id)
                elif obj.get("refunded") or int(obj.get("amount_refunded") or 0) >= int(obj.get("amount") or 1):
                    _reverter(db, order, "reembolsado", request_id)
    db.commit()
    return {"received": True}


# ---------------------------------------------------------------- buyer's return


def confirmar(db: Session, session_id: str, actor, request_id=None):
    """Back from Stripe: asks Stripe about the session, so the plugin shows up even before the webhook."""
    order = db.scalar(select(PluginPedidoStripeModel).where(PluginPedidoStripeModel.stripe_session_id == session_id))
    if order is None or order.usuario_id != actor.id:
        raise HTTPException(404, "Pedido não encontrado.")
    if order.status == "aberto" and configurado():
        session = _api("GET", f"/checkout/sessions/{session_id}")
        if str(session.get("id")) == session_id:
            _apply_session(db, session, request_id)
            db.commit()
    return {"status": order.status, "pago": order.status == "pago"}


def pedido_da_licenca(db: Session, license_id: int):
    return db.scalar(select(PluginPedidoStripeModel).where(PluginPedidoStripeModel.licenca_id == license_id))


def checkout_aberto(order):
    return order.checkout_url if order is not None and _still_open(order) else None
