import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, DecimalException
from urllib.parse import urlsplit

import requests

from core.config import settings
from models.enums.financeiro import PagamentoStatus


logger = logging.getLogger(__name__)
API_BASE_URL = "https://api.mercadopago.com"
SAFE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PAYMENT_METHOD_PATTERN = re.compile(r"^[a-z0-9_-]{1,40}$")
PROVIDER_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


class MercadoPagoError(Exception):
    code = "provider_unknown_error"
    retryable = False

    def __init__(self, *, http_status=None, retry_after=None, payment_id=None):
        super().__init__(self.code)
        self.http_status = http_status
        self.retry_after = retry_after
        self.payment_id = payment_id


class MercadoPagoNotConfigured(MercadoPagoError):
    code = "provider_not_configured"


class MercadoPagoAuthError(MercadoPagoError):
    code = "provider_auth_error"


class MercadoPagoValidationError(MercadoPagoError):
    code = "provider_validation_error"


class MercadoPagoConflict(MercadoPagoError):
    code = "provider_conflict"


class MercadoPagoRateLimited(MercadoPagoError):
    code = "provider_rate_limited"
    retryable = True


class MercadoPagoTimeout(MercadoPagoError):
    code = "provider_timeout"
    retryable = True


class MercadoPagoUnavailable(MercadoPagoError):
    code = "provider_unavailable"
    retryable = True


class MercadoPagoInvalidResponse(MercadoPagoError):
    code = "provider_invalid_response"


@dataclass(frozen=True)
class MercadoPagoPayer:
    email: str
    first_name: str | None = None
    last_name: str | None = None
    identification_type: str | None = None
    identification_number: str | None = None

    def payload(self) -> dict:
        if not isinstance(self.email, str):
            raise MercadoPagoValidationError()
        email = self.email.strip()
        if not email or len(email) > 254 or "@" not in email:
            raise MercadoPagoValidationError()
        payload = {"email": email}
        if self.first_name:
            if not isinstance(self.first_name, str):
                raise MercadoPagoValidationError()
            payload["first_name"] = self.first_name.strip()[:100]
        if self.last_name:
            if not isinstance(self.last_name, str):
                raise MercadoPagoValidationError()
            payload["last_name"] = self.last_name.strip()[:100]
        if bool(self.identification_type) != bool(self.identification_number):
            raise MercadoPagoValidationError()
        if self.identification_type:
            if not isinstance(self.identification_type, str) or not isinstance(
                self.identification_number, str
            ):
                raise MercadoPagoValidationError()
            payload["identification"] = {
                "type": self.identification_type.strip()[:20],
                "number": self.identification_number.strip()[:40],
            }
        return payload


@dataclass(frozen=True)
class PixPaymentData:
    qr_code: str | None
    qr_code_base64: str | None
    ticket_url: str | None
    expiration_time: str | None


@dataclass(frozen=True)
class ProviderPaymentResult:
    provider_id: str
    external_reference: str | None
    currency: str | None
    status: PagamentoStatus
    provider_status: str
    status_detail: str | None
    method: str | None
    amount: Decimal
    approved_at: datetime | None
    pix: PixPaymentData | None = None
    challenge_url: str | None = None


def map_provider_status(status, status_detail=None) -> PagamentoStatus:
    value = str(status or "").strip().lower()
    detail = str(status_detail or "").strip().lower()
    if value in {"approved"} or (value == "processed" and detail == "accredited"):
        return PagamentoStatus.APROVADO
    if value in {"rejected", "failed"}:
        return PagamentoStatus.RECUSADO
    if value in {"cancelled", "canceled", "expired"}:
        return PagamentoStatus.CANCELADO
    if value in {"refunded"}:
        return PagamentoStatus.REEMBOLSADO
    if value not in {"pending", "created", "processing", "action_required", "processed"}:
        safe_value = re.sub(r"[^a-z0-9_-]", "?", value[:40]) or "missing"
        logger.warning("mercado_pago_unknown_status status=%s", safe_value)
    return PagamentoStatus.PENDENTE


def _money(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (DecimalException, ValueError, TypeError):
        raise MercadoPagoInvalidResponse() from None
    if not amount.is_finite() or amount <= 0:
        raise MercadoPagoInvalidResponse()
    return amount


def _datetime(value) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class MercadoPagoClient:
    def __init__(self, access_token=None, *, timeout=None, session=None):
        self._access_token = access_token if access_token is not None else getattr(
            settings, "MERCADO_PAGO_ACCESS_TOKEN", None
        )
        self._timeout = timeout if timeout is not None else getattr(
            settings, "MERCADO_PAGO_TIMEOUT_SECONDS", 10.0
        )
        self._session = session or requests.Session()

    def ensure_configured(self):
        if not isinstance(self._access_token, str) or not self._access_token.strip():
            raise MercadoPagoNotConfigured()

    def create_pix(
        self,
        *,
        amount: Decimal,
        external_reference: str,
        idempotency_key: str,
        payer: MercadoPagoPayer,
        expiration_time: str | None = None,
    ) -> ProviderPaymentResult:
        if expiration_time is not None and (
            not isinstance(expiration_time, str) or not 1 <= len(expiration_time) <= 40
        ):
            raise MercadoPagoValidationError()
        payment = {
            "amount": f"{_money(amount):.2f}",
            "payment_method": {"id": "pix", "type": "bank_transfer"},
        }
        if expiration_time:
            payment["expiration_time"] = expiration_time
        return self._create_order(
            amount=amount,
            external_reference=external_reference,
            idempotency_key=idempotency_key,
            payer=payer,
            payment=payment,
        )

    def create_card(
        self,
        *,
        amount: Decimal,
        external_reference: str,
        idempotency_key: str,
        payer: MercadoPagoPayer,
        card_token: str,
        payment_method_id: str,
        installments: int,
        payment_method_type: str = "credit_card",
    ) -> ProviderPaymentResult:
        if not isinstance(card_token, str) or not card_token.strip() or len(card_token) > 256:
            raise MercadoPagoValidationError()
        if not isinstance(payment_method_id, str) or not PAYMENT_METHOD_PATTERN.fullmatch(payment_method_id):
            raise MercadoPagoValidationError()
        if payment_method_type not in {"credit_card", "debit_card"}:
            raise MercadoPagoValidationError()
        if not isinstance(installments, int) or isinstance(installments, bool) or not 1 <= installments <= 24:
            raise MercadoPagoValidationError()
        payment = {
            "amount": f"{_money(amount):.2f}",
            "payment_method": {
                "id": payment_method_id,
                "type": payment_method_type,
                "token": card_token,
                "installments": installments,
            },
        }
        return self._create_order(
            amount=amount,
            external_reference=external_reference,
            idempotency_key=idempotency_key,
            payer=payer,
            payment=payment,
            transaction_security=True,
        )

    def get_order(self, provider_id: str) -> ProviderPaymentResult:
        if not isinstance(provider_id, str) or not PROVIDER_ID_PATTERN.fullmatch(provider_id):
            raise MercadoPagoValidationError()
        data = self._request("GET", f"/v1/orders/{provider_id}")
        return self._parse_result(data)

    def _create_order(
        self,
        *,
        amount,
        external_reference,
        idempotency_key,
        payer,
        payment,
        transaction_security=False,
    ):
        if not SAFE_ID_PATTERN.fullmatch(external_reference or ""):
            raise MercadoPagoValidationError()
        if not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 128:
            raise MercadoPagoValidationError()
        amount_string = f"{_money(amount):.2f}"
        payload = {
            "type": "online",
            "processing_mode": "automatic",
            "total_amount": amount_string,
            "external_reference": external_reference,
            "payer": payer.payload(),
            "transactions": {"payments": [payment]},
        }
        if transaction_security:
            payload["config"] = {
                "online": {
                    "transaction_security": {
                        "validation": "on_fraud_risk",
                        "liability_shift": "required",
                    }
                }
            }
        data = self._request(
            "POST",
            "/v1/orders",
            json=payload,
            idempotency_key=idempotency_key,
        )
        return self._parse_result(data)

    def _request(self, method, path, *, json=None, idempotency_key=None):
        self.ensure_configured()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._access_token.strip()}",
        }
        if idempotency_key:
            headers["X-Idempotency-Key"] = idempotency_key
        try:
            response = self._session.request(
                method,
                API_BASE_URL + path,
                headers=headers,
                json=json,
                timeout=self._timeout,
            )
        except requests.Timeout:
            raise MercadoPagoTimeout() from None
        except requests.ConnectionError:
            raise MercadoPagoUnavailable() from None
        except requests.RequestException:
            raise MercadoPagoUnavailable() from None
        status = response.status_code
        try:
            data = response.json()
        except (ValueError, TypeError):
            if status in {401, 403}:
                raise MercadoPagoAuthError(http_status=status) from None
            if status in {409, 423}:
                raise MercadoPagoConflict(http_status=status) from None
            if status == 429:
                raise MercadoPagoRateLimited(
                    http_status=status,
                    retry_after=response.headers.get("Retry-After"),
                ) from None
            if status >= 500:
                raise MercadoPagoUnavailable(http_status=status) from None
            raise MercadoPagoInvalidResponse(http_status=status) from None
        if 200 <= status < 300:
            if not isinstance(data, dict):
                raise MercadoPagoInvalidResponse(http_status=status)
            return data
        if status == 402 and isinstance(data, dict) and data.get("id"):
            return data
        if status in {400, 402, 422}:
            raise MercadoPagoValidationError(http_status=status)
        if status in {401, 403}:
            raise MercadoPagoAuthError(http_status=status)
        if status in {409, 423}:
            raise MercadoPagoConflict(http_status=status)
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            raise MercadoPagoRateLimited(http_status=status, retry_after=retry_after)
        if status >= 500:
            raise MercadoPagoUnavailable(http_status=status)
        raise MercadoPagoError(http_status=status)

    def _parse_result(self, data) -> ProviderPaymentResult:
        try:
            provider_id = data["id"]
            payments = data.get("transactions", {}).get("payments", [])
            payment = payments[0] if payments else {}
            order_status = data.get("status")
            order_detail = data.get("status_detail")
            payment_status = payment.get("status")
            payment_detail = payment.get("status_detail")
            if order_detail == "partially_refunded":
                provider_status = order_status
                status_detail = order_detail
            elif payment_status == "charged_back" or str(payment_detail or "").startswith(
                "charged_back"
            ):
                provider_status = payment_status
                status_detail = payment_detail
            else:
                provider_status = payment_status or order_status
                status_detail = payment_detail or order_detail
            amount = _money(payment.get("amount", data.get("total_amount")))
            method_data = payment.get("payment_method") or {}
            method = method_data.get("id")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise MercadoPagoInvalidResponse() from None
        if (
            not isinstance(provider_id, str)
            or not PROVIDER_ID_PATTERN.fullmatch(provider_id)
            or provider_status is None
        ):
            raise MercadoPagoInvalidResponse()
        normalized_status = map_provider_status(provider_status, status_detail)
        pix = None
        if method == "pix":
            pix = PixPaymentData(
                qr_code=method_data.get("qr_code"),
                qr_code_base64=method_data.get("qr_code_base64") or method_data.get("qr_code_based64"),
                ticket_url=method_data.get("ticket_url"),
                expiration_time=payment.get("expiration_time") or payment.get("date_of_expiration"),
            )
        challenge_url = None
        security = method_data.get("transaction_security") or {}
        candidate_url = security.get("url") if isinstance(security, dict) else None
        if isinstance(candidate_url, str):
            parts = urlsplit(candidate_url)
            hostname = (parts.hostname or "").lower()
            if (
                parts.scheme == "https"
                and parts.netloc
                and not parts.username
                and (hostname == "mercadopago.com" or hostname.startswith("www.mercadopago.")
                     or ".mercadopago." in hostname)
            ):
                challenge_url = candidate_url
        return ProviderPaymentResult(
            provider_id=provider_id,
            external_reference=str(data.get("external_reference"))[:64]
            if data.get("external_reference") is not None
            else None,
            currency=str(
                data.get("currency")
                or data.get("currency_id")
                or payment.get("currency_id")
            )[:3]
            if any(
                value is not None
                for value in (
                    data.get("currency"),
                    data.get("currency_id"),
                    payment.get("currency_id"),
                )
            )
            else None,
            status=normalized_status,
            provider_status=str(provider_status)[:40],
            status_detail=str(status_detail)[:100] if status_detail is not None else None,
            method=str(method)[:40] if method is not None else None,
            amount=amount,
            approved_at=_datetime(payment.get("date_approved"))
            if normalized_status == PagamentoStatus.APROVADO
            else None,
            pix=pix,
            challenge_url=challenge_url,
        )
