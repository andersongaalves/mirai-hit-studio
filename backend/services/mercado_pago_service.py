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


def _tentativa(db: Session, payment_id: int, metodo: str) -> PagamentoModel:
    payment = db.get(PagamentoModel, payment_id)
    if payment is None:
        raise financial_service.FinanceiroInvalido("Pagamento nao encontrado.")
    if payment.provider != PROVIDER or payment.metodo != metodo:
        raise financial_service.FinanceiroConflito("Tentativa incompativel com o provider.")
    if not payment.provider_idempotency_key or not payment.provider_reference:
        raise financial_service.FinanceiroConflito("Tentativa sem identidade financeira.")
    if payment.provider_payment_id:
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
    if payment.provider_payment_id and payment.provider_payment_id != result.provider_id:
        db.rollback()
        raise financial_service.FinanceiroConflito("Tentativa vinculada a outro pagamento provider.")
    try:
        payment.provider_payment_id = result.provider_id
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


def _log_error(error: MercadoPagoError, payment: PagamentoModel, request_id: str | None):
    logger.warning(
        "mercado_pago_request_failed category=%s payment_id=%s cobranca_id=%s http_status=%s request_id=%s",
        error.code,
        payment.id,
        payment.cobranca_id,
        error.http_status,
        request_id,
    )
