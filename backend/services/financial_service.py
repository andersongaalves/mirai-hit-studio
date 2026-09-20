from datetime import datetime, timezone
from decimal import Decimal, DecimalException, ROUND_DOWN, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from models.enums.financeiro import CobrancaStatus, PagamentoStatus, PagamentoTipo
from models.enums.proposta import PropostaStatus
from models.financeiro import CobrancaModel, PagamentoModel
from services import proposta_service


CENTAVO = Decimal("0.01")


class FinanceiroInvalido(Exception):
    pass


class FinanceiroConflito(Exception):
    pass


def normalizar_valor(value, *, positivo=True) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(CENTAVO, rounding=ROUND_HALF_UP)
    except (DecimalException, ValueError, TypeError):
        raise FinanceiroInvalido("Valor monetario invalido.") from None
    if not amount.is_finite() or (positivo and amount <= 0) or amount < 0:
        raise FinanceiroInvalido("Valor monetario invalido.")
    return amount


def dividir_50_50(value) -> tuple[Decimal, Decimal]:
    total = normalizar_valor(value)
    entrada = (total / 2).quantize(CENTAVO, rounding=ROUND_DOWN)
    saldo = total - entrada
    if entrada <= 0:
        raise FinanceiroInvalido("Valor insuficiente para divisao em duas parcelas.")
    return entrada, saldo


def valor_pago(cobranca: CobrancaModel) -> Decimal:
    return sum(
        (
            normalizar_valor(payment.valor)
            for payment in cobranca.pagamentos
            if payment.status == PagamentoStatus.APROVADO.value
        ),
        Decimal("0.00"),
    )


def saldo_pendente(cobranca: CobrancaModel) -> Decimal:
    saldo = normalizar_valor(cobranca.valor_total) - valor_pago(cobranca)
    if saldo < 0:
        raise FinanceiroConflito("Pagamento acima do valor contratado requer conciliacao.")
    return saldo


def valor_para_pagamento(cobranca: CobrancaModel, tipo: PagamentoTipo | str) -> Decimal:
    try:
        tipo_value = PagamentoTipo(tipo)
    except ValueError:
        raise FinanceiroInvalido("Tipo de pagamento invalido.") from None
    total = normalizar_valor(cobranca.valor_total)
    pago = valor_pago(cobranca)
    saldo = total - pago
    if saldo <= 0:
        raise FinanceiroConflito("Cobranca sem saldo pendente.")
    if tipo_value == PagamentoTipo.INTEGRAL:
        if pago:
            raise FinanceiroConflito("Pagamento integral indisponivel apos pagamento parcial.")
        return total
    if tipo_value == PagamentoTipo.ENTRADA:
        if pago:
            raise FinanceiroConflito("Entrada indisponivel apos pagamento aprovado.")
        return dividir_50_50(total)[0]
    if pago == 0:
        raise FinanceiroConflito("Saldo disponivel somente apos pagamento parcial.")
    return saldo


def status_calculado(cobranca: CobrancaModel) -> CobrancaStatus:
    if cobranca.status == CobrancaStatus.CANCELADA.value:
        return CobrancaStatus.CANCELADA
    total = normalizar_valor(cobranca.valor_total)
    paid = valor_pago(cobranca)
    if paid > total:
        raise FinanceiroConflito("Pagamento acima do valor contratado requer conciliacao.")
    if paid == 0:
        return CobrancaStatus.PENDENTE
    if paid < total:
        return CobrancaStatus.PARCIALMENTE_PAGA
    return CobrancaStatus.PAGA


def sincronizar_status(cobranca: CobrancaModel) -> CobrancaStatus:
    status = status_calculado(cobranca)
    cobranca.status = status.value
    return status


def buscar_por_proposta(db: Session, proposta_id: int):
    return db.scalar(select(CobrancaModel).where(CobrancaModel.proposta_id == proposta_id))


def criar_para_proposta(db: Session, proposta, *, cliente_id=None) -> CobrancaModel:
    if proposta.status not in (PropostaStatus.ENVIADA.value, PropostaStatus.ACEITA.value):
        raise FinanceiroConflito("A proposta ainda nao gera obrigacao financeira.")
    existente = buscar_por_proposta(db, proposta.id)
    resposta = proposta_service._resposta(proposta)
    total = normalizar_valor(proposta_service.calcular_totais(resposta.itens).total)
    if existente is not None:
        if normalizar_valor(existente.valor_total) != total:
            raise FinanceiroConflito("Cobranca existente diverge do valor contratado.")
        return existente
    cobranca = CobrancaModel(
        proposta_id=proposta.id,
        cliente_id=cliente_id,
        valor_total=total,
        moeda="BRL",
        status=CobrancaStatus.PENDENTE.value,
    )
    db.add(cobranca)
    db.flush()
    return cobranca


def registrar_pagamento(
    db: Session,
    cobranca_id: int,
    *,
    tipo: PagamentoTipo | str,
    valor,
    status: PagamentoStatus | str = PagamentoStatus.PENDENTE,
    metodo: str | None = None,
    provider: str | None = None,
    provider_payment_id: str | None = None,
    provider_reference: str | None = None,
) -> PagamentoModel:
    cobranca = db.scalar(
        select(CobrancaModel).where(CobrancaModel.id == cobranca_id).with_for_update()
    )
    if cobranca is None:
        raise FinanceiroInvalido("Cobranca nao encontrada.")
    if cobranca.status == CobrancaStatus.CANCELADA.value:
        raise FinanceiroConflito("Cobranca cancelada nao aceita pagamentos.")
    try:
        tipo_value = PagamentoTipo(tipo).value
        status_value = PagamentoStatus(status).value
    except ValueError:
        raise FinanceiroInvalido("Tipo ou status de pagamento invalido.") from None
    amount = normalizar_valor(valor)
    if status_value == PagamentoStatus.APROVADO.value:
        if valor_pago(cobranca) + amount > normalizar_valor(cobranca.valor_total):
            raise FinanceiroConflito("Pagamento acima do valor contratado requer conciliacao.")
    payment = PagamentoModel(
        cobranca=cobranca,
        tipo=tipo_value,
        valor=amount,
        status=status_value,
        metodo=metodo,
        provider=provider,
        provider_payment_id=provider_payment_id,
        provider_reference=provider_reference,
        aprovado_em=datetime.now(timezone.utc)
        if status_value == PagamentoStatus.APROVADO.value
        else None,
    )
    db.add(payment)
    db.flush()
    sincronizar_status(cobranca)
    db.flush()
    return payment
