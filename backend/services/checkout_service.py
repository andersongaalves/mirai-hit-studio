from urllib.parse import urlsplit
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from integrations.mercado_pago import MercadoPagoClient, MercadoPagoPayer, ProviderPaymentResult
from models.enums.financeiro import CobrancaStatus, PagamentoStatus, PagamentoTipo
from models.enums.proposta import PropostaStatus
from models.financeiro import CobrancaModel, PagamentoModel
from schemas.checkout import (
    CheckoutAttempt,
    CheckoutOption,
    CheckoutPaymentResponse,
    CheckoutPixData,
    CheckoutStatus,
    CheckoutSummary,
)
from services import financial_service, mercado_pago_service


class CheckoutNaoEncontrado(Exception):
    pass


class CheckoutIndisponivel(Exception):
    pass


class CheckoutConflito(Exception):
    pass


OPTION_TITLES = {
    PagamentoTipo.INTEGRAL: "Pagamento completo",
    PagamentoTipo.ENTRADA: "Entrada",
    PagamentoTipo.SALDO: "Saldo restante",
}


def _token(value: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise CheckoutNaoEncontrado("Checkout nao encontrado.") from None


def _query(token: str, *, lock=False):
    query = (
        select(CobrancaModel)
        .where(CobrancaModel.referencia_externa == _token(token))
        .options(
            joinedload(CobrancaModel.proposta),
            joinedload(CobrancaModel.cliente),
            selectinload(CobrancaModel.pagamentos),
        )
    )
    return query.with_for_update() if lock else query


def carregar(db: Session, token: str, *, lock=False) -> CobrancaModel:
    cobranca = db.scalar(_query(token, lock=lock))
    if cobranca is None:
        raise CheckoutNaoEncontrado("Checkout nao encontrado.")
    if cobranca.proposta is None or cobranca.proposta.status != PropostaStatus.ACEITA.value:
        raise CheckoutIndisponivel("Checkout indisponivel.")
    return cobranca


def _tentativa_atual(cobranca: CobrancaModel) -> PagamentoModel | None:
    candidates = [
        payment
        for payment in cobranca.pagamentos
        if payment.provider == mercado_pago_service.PROVIDER
        and payment.status == PagamentoStatus.PENDENTE.value
    ]
    return max(candidates, key=lambda payment: payment.id or 0, default=None)


def _ultimo_pagamento(cobranca: CobrancaModel) -> PagamentoModel | None:
    return max(cobranca.pagamentos, key=lambda payment: payment.id or 0, default=None)


def _options(cobranca: CobrancaModel) -> list[CheckoutOption]:
    if cobranca.status in {CobrancaStatus.PAGA.value, CobrancaStatus.CANCELADA.value}:
        return []
    tipos = (
        [PagamentoTipo.SALDO]
        if financial_service.valor_pago(cobranca) > 0
        else [PagamentoTipo.INTEGRAL, PagamentoTipo.ENTRADA]
    )
    return [
        CheckoutOption(
            tipo=tipo.value,
            titulo=OPTION_TITLES[tipo],
            valor=financial_service.valor_para_pagamento(cobranca, tipo),
        )
        for tipo in tipos
    ]


def resumo(db: Session, token: str) -> CheckoutSummary:
    cobranca = carregar(db, token)
    pago = financial_service.valor_pago(cobranca)
    saldo = financial_service.saldo_pendente(cobranca)
    pending = _tentativa_atual(cobranca)
    return CheckoutSummary(
        proposta_numero=cobranca.proposta.numero,
        descricao=cobranca.proposta.objeto or "Proposta comercial",
        valor_total=cobranca.valor_total,
        valor_pago=pago,
        saldo=saldo,
        moeda=cobranca.moeda,
        status=cobranca.status,
        opcoes=_options(cobranca),
        tentativa=CheckoutAttempt(
            metodo="cartao" if pending.metodo != "pix" else "pix",
            tipo=pending.tipo,
            status="processando",
            recuperavel=bool(pending.provider_order_id),
        ) if pending else None,
    )


def status(db: Session, token: str) -> CheckoutStatus:
    cobranca = carregar(db, token)
    latest = _ultimo_pagamento(cobranca)
    payment_status = None
    if latest is not None:
        payment_status = {
            PagamentoStatus.PENDENTE.value: "processando",
            PagamentoStatus.RECUSADO.value: "recusado",
            PagamentoStatus.CANCELADO.value: "recusado",
            PagamentoStatus.APROVADO.value: "aprovado",
            PagamentoStatus.REEMBOLSADO.value: None,
        }[latest.status]
    return CheckoutStatus(
        status=cobranca.status,
        valor_pago=financial_service.valor_pago(cobranca),
        saldo=financial_service.saldo_pendente(cobranca),
        pagamento_status=payment_status,
    )


def _payer(cobranca: CobrancaModel, *, email=None, identification_type=None, identification_number=None):
    snapshot = cobranca.proposta.cliente_snapshot or {}
    customer = snapshot.get("cliente") if isinstance(snapshot, dict) else {}
    customer = customer if isinstance(customer, dict) else {}
    stored_email = cobranca.cliente.email if cobranca.cliente and cobranca.cliente.email else customer.get("email")
    name = str(customer.get("nome") or "").strip().split(maxsplit=1)
    return MercadoPagoPayer(
        email=str(email or stored_email or ""),
        first_name=name[0] if name else None,
        last_name=name[1] if len(name) > 1 else None,
        identification_type=identification_type,
        identification_number=identification_number,
    )


def _get_or_create_attempt(db: Session, cobranca: CobrancaModel, *, tipo: str, metodo: str):
    # The charge lock serializes checkout submissions. Existing outbound paths remain unchanged.
    locked = carregar(db, cobranca.referencia_externa, lock=True)
    db.expire(locked, ["pagamentos", "status", "valor_total"])
    pending = db.scalar(
        select(PagamentoModel)
        .where(
            PagamentoModel.cobranca_id == locked.id,
            PagamentoModel.provider == mercado_pago_service.PROVIDER,
            PagamentoModel.status == PagamentoStatus.PENDENTE.value,
        )
        .order_by(PagamentoModel.id.desc())
        .limit(1)
    )
    if pending is not None:
        pending_method = "pix" if pending.metodo == "pix" else "cartao"
        if pending.tipo != tipo or pending_method != metodo:
            db.rollback()
            raise CheckoutConflito("Ja existe um pagamento em processamento.")
        db.rollback()
        return pending.id, True
    try:
        amount = financial_service.valor_para_pagamento(locked, tipo)
    except (financial_service.FinanceiroInvalido, financial_service.FinanceiroConflito) as error:
        db.rollback()
        raise CheckoutConflito(str(error)) from None
    payment = financial_service.registrar_pagamento(
        db,
        locked.id,
        tipo=tipo,
        valor=amount,
        status=PagamentoStatus.PENDENTE,
        metodo=metodo,
        provider=mercado_pago_service.PROVIDER,
        provider_reference=None,
    )
    from uuid import uuid4

    key = str(uuid4())
    payment.provider_reference = key
    payment.provider_idempotency_key = key
    db.commit()
    return payment.id, False


def _result_response(db: Session, payment_id: int, result: ProviderPaymentResult):
    payment = db.get(PagamentoModel, payment_id)
    status_name = "pending"
    if result.status == PagamentoStatus.APROVADO:
        status_name = "approved"
    elif result.status in {PagamentoStatus.RECUSADO, PagamentoStatus.CANCELADO}:
        status_name = "rejected"
    elif result.provider_status == "action_required" and result.challenge_url:
        status_name = "action_required"
    pix = None
    if result.pix:
        pix = CheckoutPixData(
            qr_code=result.pix.qr_code,
            qr_code_base64=result.pix.qr_code_base64,
            ticket_url=result.pix.ticket_url,
            expiration_time=result.pix.expiration_time,
        )
    return CheckoutPaymentResponse(
        status=status_name,
        checkout_status=payment.cobranca.status,
        payment_option=payment.tipo,
        valor=payment.valor,
        moeda=payment.cobranca.moeda,
        pix=pix,
        challenge_url=result.challenge_url,
    )


def criar_pix(db: Session, token: str, tipo: str, *, client=None, request_id=None):
    provider = client or MercadoPagoClient()
    provider.ensure_configured()
    cobranca = carregar(db, token)
    payment_id, reused = _get_or_create_attempt(db, cobranca, tipo=tipo, metodo="pix")
    if reused:
        return recuperar(db, token, client=provider, request_id=request_id)
    execution = mercado_pago_service.enviar_pix(
        db,
        payment_id,
        payer=_payer(cobranca),
        client=provider,
        request_id=request_id,
    )
    return _result_response(db, payment_id, execution.result)


def criar_cartao(db: Session, token: str, dados, *, client=None, request_id=None):
    provider = client or MercadoPagoClient()
    provider.ensure_configured()
    cobranca = carregar(db, token)
    payment_id, reused = _get_or_create_attempt(
        db, cobranca, tipo=dados.payment_option, metodo="cartao"
    )
    if reused:
        return recuperar(db, token, client=provider, request_id=request_id)
    execution = mercado_pago_service.enviar_cartao(
        db,
        payment_id,
        payer=_payer(
            cobranca,
            email=dados.payer_email,
            identification_type=dados.identification_type,
            identification_number=dados.identification_number,
        ),
        card_token=dados.card_token,
        payment_method_id=dados.payment_method_id,
        payment_method_type=dados.payment_method_type,
        installments=dados.installments,
        client=provider,
        request_id=request_id,
    )
    return _result_response(db, payment_id, execution.result)


def recuperar(db: Session, token: str, *, client=None, request_id=None):
    cobranca = carregar(db, token)
    payment = _tentativa_atual(cobranca)
    if payment is None:
        raise CheckoutConflito("Nao existe pagamento em processamento.")
    if not payment.provider_order_id:
        raise CheckoutConflito("Pagamento requer conciliacao antes de nova tentativa.")
    reconciled = mercado_pago_service.reconcile_payment(
        db, payment.id, client=client, request_id=request_id
    )
    return _result_response(db, payment.id, reconciled.provider_result)


def link_por_proposta(db: Session, proposta_id: int, base_url: str) -> str:
    cobranca = db.scalar(
        select(CobrancaModel).where(CobrancaModel.proposta_id == proposta_id)
    )
    if cobranca is None:
        raise CheckoutNaoEncontrado("Cobranca nao encontrada para esta proposta.")
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise CheckoutIndisponivel("URL publica do checkout nao configurada.")
    return f"{base_url.rstrip('/')}/checkout/{cobranca.referencia_externa}"
