import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from integrations.mercado_pago import (
    MercadoPagoClient,
    MercadoPagoError,
    MercadoPagoPayer,
    ProviderPaymentResult,
)
from models.enums.financeiro import CobrancaStatus, PagamentoStatus, PagamentoTipo
from models.financeiro import CobrancaModel, PagamentoModel
from services import financial_service


logger = logging.getLogger(__name__)
PROVIDER = "mercado_pago"


@dataclass(frozen=True)
class PaymentExecution:
    payment_id: int
    result: ProviderPaymentResult


@dataclass(frozen=True)
class ReconciliationResult:
    payment_id: int
    previous_status: str
    current_status: str
    changed: bool
    outcome: str
    provider_result: ProviderPaymentResult


class ReconciliationRequired(Exception):
    def __init__(self, reason: str, payment_id: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.payment_id = payment_id


class ReconciliationConflict(Exception):
    def __init__(self, reason: str, payment_id: int | None = None):
        super().__init__(reason)
        self.reason = reason
        self.payment_id = payment_id


def criar_tentativa(
    db: Session,
    cobranca_id: int,
    *,
    tipo: PagamentoTipo | str,
    metodo: str,
) -> PagamentoModel:
    cobranca = db.scalar(
        select(CobrancaModel).where(CobrancaModel.id == cobranca_id).with_for_update()
    )
    if cobranca is None:
        raise financial_service.FinanceiroInvalido("Cobranca nao encontrada.")
    if cobranca.status == CobrancaStatus.CANCELADA.value:
        raise financial_service.FinanceiroConflito("Cobranca cancelada nao aceita pagamentos.")
    amount = financial_service.valor_para_pagamento(cobranca, tipo)
    key = str(uuid4())
    payment = financial_service.registrar_pagamento(
        db,
        cobranca.id,
        tipo=tipo,
        valor=amount,
        status=PagamentoStatus.PENDENTE,
        metodo=metodo,
        provider=PROVIDER,
        provider_reference=key,
    )
    payment.provider_idempotency_key = key
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)
    return payment


def criar_pix(
    db: Session,
    cobranca_id: int,
    *,
    tipo: PagamentoTipo | str,
    payer: MercadoPagoPayer,
    expiration_time: str | None = None,
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> PaymentExecution:
    provider = client or MercadoPagoClient()
    provider.ensure_configured()
    payment = criar_tentativa(db, cobranca_id, tipo=tipo, metodo="pix")
    return enviar_pix(
        db,
        payment.id,
        payer=payer,
        expiration_time=expiration_time,
        client=provider,
        request_id=request_id,
    )


def enviar_pix(
    db: Session,
    payment_id: int,
    *,
    payer: MercadoPagoPayer,
    expiration_time: str | None = None,
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> PaymentExecution:
    payment = _tentativa(db, payment_id, "pix")
    provider = client or MercadoPagoClient()
    try:
        result = provider.create_pix(
            amount=payment.valor,
            external_reference=payment.provider_reference,
            idempotency_key=payment.provider_idempotency_key,
            payer=payer,
            expiration_time=expiration_time,
        )
    except MercadoPagoError as error:
        error.payment_id = payment.id
        _log_error(error, payment, request_id)
        raise
    return PaymentExecution(payment.id, _persistir_resultado(db, payment.id, result))


def criar_cartao(
    db: Session,
    cobranca_id: int,
    *,
    tipo: PagamentoTipo | str,
    payer: MercadoPagoPayer,
    card_token: str,
    payment_method_id: str,
    installments: int,
    payment_method_type: str = "credit_card",
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> PaymentExecution:
    provider = client or MercadoPagoClient()
    provider.ensure_configured()
    payment = criar_tentativa(db, cobranca_id, tipo=tipo, metodo="cartao")
    return enviar_cartao(
        db,
        payment.id,
        payer=payer,
        card_token=card_token,
        payment_method_id=payment_method_id,
        installments=installments,
        payment_method_type=payment_method_type,
        client=provider,
        request_id=request_id,
    )


def enviar_cartao(
    db: Session,
    payment_id: int,
    *,
    payer: MercadoPagoPayer,
    card_token: str,
    payment_method_id: str,
    installments: int,
    payment_method_type: str = "credit_card",
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> PaymentExecution:
    payment = _tentativa(db, payment_id, "cartao")
    provider = client or MercadoPagoClient()
    try:
        result = provider.create_card(
            amount=payment.valor,
            external_reference=payment.provider_reference,
            idempotency_key=payment.provider_idempotency_key,
            payer=payer,
            card_token=card_token,
            payment_method_id=payment_method_id,
            installments=installments,
            payment_method_type=payment_method_type,
        )
    except MercadoPagoError as error:
        error.payment_id = payment.id
        _log_error(error, payment, request_id)
        raise
    return PaymentExecution(payment.id, _persistir_resultado(db, payment.id, result))


def consultar_order(provider_id: str, *, client: MercadoPagoClient | None = None):
    return (client or MercadoPagoClient()).get_order(provider_id)


def reconcile_payment(
    db: Session,
    payment_id: int,
    *,
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> ReconciliationResult:
    payment = db.get(PagamentoModel, payment_id)
    if payment is None:
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    provider_order_id = payment.provider_order_id
    db.rollback()
    if not provider_order_id:
        _mark_reconciliation(db, payment_id, "required", "missing_provider_order_id")
        raise ReconciliationRequired("missing_provider_order_id", payment_id)
    provider = client or MercadoPagoClient()
    try:
        result = provider.get_order(provider_order_id)
    except MercadoPagoError as error:
        logger.warning(
            "mercado_pago_reconciliation_failed category=%s payment_id=%s request_id=%s",
            error.code,
            payment_id,
            request_id,
        )
        raise
    return _apply_reconciliation(
        db,
        payment_id,
        result,
        expected_order_id=provider_order_id,
    )


def reconcile_order(
    db: Session,
    provider_order_id: str,
    *,
    client: MercadoPagoClient | None = None,
    request_id: str | None = None,
) -> ReconciliationResult:
    provider = client or MercadoPagoClient()
    try:
        result = provider.get_order(provider_order_id)
    except MercadoPagoError as error:
        logger.warning(
            "mercado_pago_webhook_lookup_failed category=%s provider_order_id=%s request_id=%s",
            error.code,
            provider_order_id,
            request_id,
        )
        raise
    if result.provider_id != provider_order_id:
        raise ReconciliationConflict("provider_order_id_mismatch")

    payment = db.scalar(
        select(PagamentoModel).where(
            PagamentoModel.provider_order_id == provider_order_id
        )
    )
    if payment is None and result.external_reference:
        matches = db.scalars(
            select(PagamentoModel)
            .where(PagamentoModel.provider_reference == result.external_reference)
            .limit(2)
        ).all()
        if len(matches) > 1:
            db.rollback()
            raise ReconciliationConflict("ambiguous_external_reference")
        payment = matches[0] if matches else None
    payment_id = payment.id if payment is not None else None
    db.rollback()
    if payment_id is None:
        raise ReconciliationConflict("payment_not_found")
    return _apply_reconciliation(
        db,
        payment_id,
        result,
        expected_order_id=provider_order_id,
    )


def _tentativa(db: Session, payment_id: int, metodo: str) -> PagamentoModel:
    payment = db.get(PagamentoModel, payment_id)
    if payment is None:
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    if payment.provider != PROVIDER or payment.metodo != metodo:
        raise financial_service.FinanceiroConflito("Tentativa incompativel com o provider.")
    if not payment.provider_idempotency_key or not payment.provider_reference:
        raise financial_service.FinanceiroConflito("Tentativa sem identidade financeira.")
    if payment.provider_order_id:
        raise financial_service.FinanceiroConflito("Tentativa ja registrada no provider.")
    return payment


def _persistir_resultado(db: Session, payment_id: int, result: ProviderPaymentResult):
    payment = db.scalar(
        select(PagamentoModel).where(PagamentoModel.id == payment_id).with_for_update()
    )
    if payment is None:
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    if financial_service.normalizar_valor(payment.valor) != result.amount:
        db.rollback()
        raise financial_service.FinanceiroConflito("Valor retornado pelo provider diverge da tentativa.")
    if payment.provider_order_id and payment.provider_order_id != result.provider_id:
        db.rollback()
        raise financial_service.FinanceiroConflito("Tentativa vinculada a outro pagamento provider.")
    try:
        payment.provider_order_id = result.provider_id
        payment.status = result.status.value
        if result.method:
            payment.metodo = result.method
        if result.status == PagamentoStatus.APROVADO:
            payment.aprovado_em = result.approved_at or datetime.now(timezone.utc)
        elif result.status == PagamentoStatus.REEMBOLSADO:
            payment.reembolsado_em = datetime.now(timezone.utc)
        financial_service.sincronizar_status(payment.cobranca)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(payment)
    return result


def _apply_reconciliation(
    db: Session,
    payment_id: int,
    result: ProviderPaymentResult,
    *,
    expected_order_id: str,
) -> ReconciliationResult:
    payment = db.scalar(
        select(PagamentoModel)
        .where(PagamentoModel.id == payment_id)
        .with_for_update()
    )
    if payment is None:
        db.rollback()
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    reason = _identity_conflict(payment, result, expected_order_id)
    if reason:
        return _raise_conflict(db, payment, reason)

    incoming, reason = _provider_state(result)
    if reason:
        return _raise_conflict(db, payment, reason)

    previous = payment.status
    next_status, outcome = _safe_transition(previous, incoming.value)
    if outcome == "conflict":
        return _raise_conflict(db, payment, "invalid_status_transition")

    payment.provider_order_id = result.provider_id
    payment.reconciliation_status = None
    payment.reconciliation_reason = None
    changed = next_status != previous
    if changed:
        payment.status = next_status
        if incoming == PagamentoStatus.APROVADO:
            payment.aprovado_em = result.approved_at or datetime.now(timezone.utc)
        elif incoming == PagamentoStatus.REEMBOLSADO:
            payment.reembolsado_em = datetime.now(timezone.utc)
    try:
        financial_service.sincronizar_status(payment.cobranca)
        db.commit()
    except financial_service.FinanceiroConflito:
        db.rollback()
        _mark_reconciliation(db, payment_id, "conflict", "overpayment")
        raise ReconciliationConflict("overpayment", payment_id) from None
    except Exception:
        db.rollback()
        raise
    return ReconciliationResult(
        payment_id=payment_id,
        previous_status=previous,
        current_status=next_status,
        changed=changed,
        outcome=outcome,
        provider_result=result,
    )


def _identity_conflict(
    payment: PagamentoModel,
    result: ProviderPaymentResult,
    expected_order_id: str,
) -> str | None:
    if payment.provider != PROVIDER:
        return "provider_mismatch"
    if result.provider_id != expected_order_id:
        return "provider_order_id_mismatch"
    if payment.provider_order_id and payment.provider_order_id != result.provider_id:
        return "provider_order_id_mismatch"
    if not result.external_reference or result.external_reference != payment.provider_reference:
        return "external_reference_mismatch"
    if financial_service.normalizar_valor(payment.valor) != result.amount:
        return "amount_mismatch"
    if result.currency != payment.cobranca.moeda or result.currency != "BRL":
        return "currency_mismatch"
    return None


def _provider_state(
    result: ProviderPaymentResult,
) -> tuple[PagamentoStatus, str | None]:
    status = result.provider_status.strip().lower()
    detail = (result.status_detail or "").strip().lower()
    if "partially_refunded" in {status, detail}:
        return PagamentoStatus.PENDENTE, "partial_refund_unsupported"
    if status == "charged_back" or detail.startswith("charged_back"):
        return PagamentoStatus.PENDENTE, "chargeback_unsupported"
    if status == "approved" or (status == "processed" and detail == "accredited"):
        return PagamentoStatus.APROVADO, None
    if status == "refunded":
        return PagamentoStatus.REEMBOLSADO, None
    if status in {"rejected", "failed"}:
        return PagamentoStatus.RECUSADO, None
    if status in {"cancelled", "canceled", "expired"}:
        return PagamentoStatus.CANCELADO, None
    if status in {"pending", "created", "processing", "action_required"}:
        return PagamentoStatus.PENDENTE, None
    return PagamentoStatus.PENDENTE, "unsupported_provider_status"


def _safe_transition(current: str, incoming: str) -> tuple[str, str]:
    if current == incoming:
        return current, "unchanged"
    if current == PagamentoStatus.REEMBOLSADO.value:
        return current, "stale_ignored"
    if current == PagamentoStatus.APROVADO.value:
        if incoming == PagamentoStatus.REEMBOLSADO.value:
            return incoming, "updated"
        return current, "stale_ignored"
    if current in {
        PagamentoStatus.RECUSADO.value,
        PagamentoStatus.CANCELADO.value,
    }:
        if incoming == PagamentoStatus.PENDENTE.value:
            return current, "stale_ignored"
        if incoming in {
            PagamentoStatus.APROVADO.value,
            PagamentoStatus.REEMBOLSADO.value,
            PagamentoStatus.RECUSADO.value,
            PagamentoStatus.CANCELADO.value,
        }:
            return incoming, "updated"
        return current, "conflict"
    if current == PagamentoStatus.PENDENTE.value:
        return incoming, "updated"
    return current, "conflict"


def _raise_conflict(db: Session, payment: PagamentoModel, reason: str):
    payment.reconciliation_status = "conflict"
    payment.reconciliation_reason = reason
    payment_id = payment.id
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    raise ReconciliationConflict(reason, payment_id)


def _mark_reconciliation(db: Session, payment_id: int, status: str, reason: str) -> None:
    payment = db.scalar(
        select(PagamentoModel)
        .where(PagamentoModel.id == payment_id)
        .with_for_update()
    )
    if payment is None:
        db.rollback()
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    payment.reconciliation_status = status
    payment.reconciliation_reason = reason
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise


def _log_error(error: MercadoPagoError, payment: PagamentoModel, request_id: str | None):
    logger.warning(
        "mercado_pago_request_failed category=%s payment_id=%s cobranca_id=%s http_status=%s request_id=%s",
        error.code,
        payment.id,
        payment.cobranca_id,
        error.http_status,
        request_id,
    )
