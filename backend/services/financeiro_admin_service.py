from datetime import datetime
from decimal import Decimal
from math import ceil

from core.config import settings
from models.cliente import ClienteModel
from models.enums.financeiro import CobrancaStatus, PagamentoStatus
from models.financeiro import CobrancaModel, PagamentoModel
from models.orcamento import OrcamentoModel
from models.proposta import PropostaModel
from services import (
    audit_service,
    checkout_service,
    financial_service,
    producao_liberacao_service,
)
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

ZERO = Decimal("0.00")


def _paid_subquery():
    return (
        select(
            PagamentoModel.cobranca_id.label("cobranca_id"),
            func.sum(
                case(
                    (PagamentoModel.status == PagamentoStatus.APROVADO.value, PagamentoModel.valor),
                    else_=0,
                )
            ).label("valor_pago"),
        )
        .group_by(PagamentoModel.cobranca_id)
        .subquery()
    )


def _money(value) -> Decimal:
    return financial_service.normalizar_valor(value or ZERO, positivo=False)


def _snapshot(cobranca: CobrancaModel) -> dict:
    value = cobranca.proposta.cliente_snapshot
    return value if isinstance(value, dict) else {}


def _cliente_nome(cobranca: CobrancaModel) -> str:
    if cobranca.cliente and cobranca.cliente.nome:
        return cobranca.cliente.nome
    snapshot = _snapshot(cobranca)
    return str(snapshot.get("nome") or snapshot.get("nome_cliente") or "Cliente não identificado")


def _cliente_email(cobranca: CobrancaModel) -> str | None:
    if cobranca.cliente and cobranca.cliente.email:
        return cobranca.cliente.email
    snapshot = _snapshot(cobranca)
    value = snapshot.get("email")
    return str(value) if value else None


def _reconciliation_status(cobranca: CobrancaModel) -> str | None:
    statuses = {payment.reconciliation_status for payment in cobranca.pagamentos}
    if "conflict" in statuses:
        return "conflict"
    if "required" in statuses:
        return "required"
    return None


def _filtro_ambiente(ambiente: str):
    test_budget = OrcamentoModel.is_test.is_(True)
    test_charge = CobrancaModel.proposta.has(PropostaModel.orcamento.has(test_budget))
    if ambiente == 'real':
        return ~test_charge
    if ambiente == 'teste':
        return test_charge
    return None


def resumo(db: Session, *, ambiente: str = 'real'):
    paid = _paid_subquery()
    ambiente_filter = _filtro_ambiente(ambiente)
    saldo = CobrancaModel.valor_total - func.coalesce(paid.c.valor_pago, 0)
    valor_a_receber = db.scalar(
        select(func.coalesce(func.sum(saldo), 0))
        .select_from(CobrancaModel)
        .outerjoin(paid, paid.c.cobranca_id == CobrancaModel.id)
        .where(CobrancaModel.status != CobrancaStatus.CANCELADA.value)
        .where(ambiente_filter if ambiente_filter is not None else True)
    )
    valor_recebido = db.scalar(
        select(func.coalesce(func.sum(PagamentoModel.valor), 0)).where(
            PagamentoModel.status == PagamentoStatus.APROVADO.value,
            PagamentoModel.cobranca.has(ambiente_filter) if ambiente_filter is not None else True,
        )
    )
    return {
        "valor_a_receber": _money(valor_a_receber),
        "valor_recebido": _money(valor_recebido),
        "cobrancas_parciais": db.scalar(
            select(func.count()).select_from(CobrancaModel).where(
                CobrancaModel.status == CobrancaStatus.PARCIALMENTE_PAGA.value,
                ambiente_filter if ambiente_filter is not None else True,
            )
        ) or 0,
        "pagamentos_em_atencao": db.scalar(
            select(func.count()).select_from(PagamentoModel).where(
                PagamentoModel.reconciliation_status.isnot(None),
                PagamentoModel.cobranca.has(ambiente_filter) if ambiente_filter is not None else True,
            )
        ) or 0,
        "total_cobrancas": db.scalar(select(func.count()).select_from(CobrancaModel).where(ambiente_filter if ambiente_filter is not None else True)) or 0,
    }


def _base_query():
    return (
        select(CobrancaModel)
        .join(CobrancaModel.proposta)
        .outerjoin(CobrancaModel.cliente)
        .options(
            selectinload(CobrancaModel.proposta),
            selectinload(CobrancaModel.cliente),
            selectinload(CobrancaModel.pagamentos),
        )
    )


def _filters(query, *, search, status, reconciliation_status, date_from, date_to):
    if search:
        term = f"%{search.strip().lower()}%"
        clauses = [
            func.lower(PropostaModel.numero).like(term),
            func.lower(PropostaModel.objeto).like(term),
            func.lower(ClienteModel.nome).like(term),
        ]
        if search.strip().isdigit():
            clauses.append(CobrancaModel.id == int(search.strip()))
        query = query.where(or_(*clauses))
    if status:
        query = query.where(CobrancaModel.status == status)
    if reconciliation_status == "clear":
        query = query.where(~CobrancaModel.pagamentos.any(PagamentoModel.reconciliation_status.isnot(None)))
    elif reconciliation_status:
        query = query.where(
            CobrancaModel.pagamentos.any(
                PagamentoModel.reconciliation_status == reconciliation_status
            )
        )
    if date_from:
        query = query.where(CobrancaModel.created_at >= date_from)
    if date_to:
        query = query.where(CobrancaModel.created_at <= date_to)
    return query


def _item(cobranca: CobrancaModel):
    paid = financial_service.valor_pago(cobranca)
    total = _money(cobranca.valor_total)
    return {
        "id": cobranca.id,
        "proposta_id": cobranca.proposta_id,
        "proposta_numero": cobranca.proposta.numero,
        "is_test": cobranca.proposta.orcamento.is_test,
        "cliente_nome": _cliente_nome(cobranca),
        "valor_total": total,
        "valor_pago": paid,
        "saldo_pendente": max(total - paid, ZERO),
        "status": cobranca.status,
        "reconciliation_status": _reconciliation_status(cobranca),
        "vencimento": cobranca.vencimento,
        "created_at": cobranca.created_at,
        "updated_at": cobranca.updated_at,
    }


def listar(
    db: Session,
    *,
    page: int,
    page_size: int,
    ambiente: str = 'real',
    search: str | None = None,
    status: str | None = None,
    reconciliation_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    query = _filters(
        _base_query().where(_filtro_ambiente(ambiente) if _filtro_ambiente(ambiente) is not None else True),
        search=search,
        status=status,
        reconciliation_status=reconciliation_status,
        date_from=date_from,
        date_to=date_to,
    )
    count_query = query.with_only_columns(func.count(func.distinct(CobrancaModel.id))).order_by(None)
    total = db.scalar(count_query) or 0
    rows = db.scalars(
        query.order_by(CobrancaModel.created_at.desc(), CobrancaModel.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).unique().all()
    return {
        "items": [_item(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


def buscar(db: Session, cobranca_id: int):
    cobranca = db.scalar(_base_query().where(CobrancaModel.id == cobranca_id))
    if cobranca is None:
        return None
    response = _item(cobranca)
    response.update({
        "cliente_email": _cliente_email(cobranca),
        "checkout_url": checkout_service.link_por_proposta(
            db, cobranca.proposta_id, settings.PUBLIC_FRONTEND_URL
        ),
        "pagamentos": [
            {
                "id": payment.id,
                "tipo": payment.tipo,
                "valor": _money(payment.valor),
                "status": payment.status,
                "metodo": payment.metodo,
                "provider": payment.provider,
                "provider_order_id": payment.provider_order_id,
                "reconciliation_status": payment.reconciliation_status,
                "reconciliation_reason": payment.reconciliation_reason,
                "aprovado_em": payment.aprovado_em,
                "reembolsado_em": payment.reembolsado_em,
                "created_at": payment.created_at,
                "updated_at": payment.updated_at,
            }
            for payment in reversed(cobranca.pagamentos)
        ],
    })
    return response


def registrar_pix_manual(db, cobranca_id, dados, *, actor, request_id=None):
    key = f"manual-pix:{dados.idempotency_key}"
    previous = db.scalar(
        select(PagamentoModel).where(PagamentoModel.provider_idempotency_key == key)
    )
    if previous is not None:
        amount_changed = (
            dados.modo == "parcial"
            and financial_service.normalizar_valor(previous.valor)
            != financial_service.normalizar_valor(dados.valor)
        )
        if (
            previous.cobranca_id != cobranca_id
            or previous.provider_reference != dados.referencia
            or amount_changed
        ):
            raise financial_service.FinanceiroConflito(
                "Referencia de repeticao ja utilizada em outro pagamento."
            )
        charge = financial_service.bloquear_cobranca(db, cobranca_id)
        return _manual_response(charge, previous, repeated=True)

    charge = financial_service.bloquear_cobranca(db, cobranca_id)
    if charge is None:
        raise financial_service.FinanceiroInvalido("Cobranca nao encontrada.")
    db.refresh(charge, ["pagamentos"])
    if any(
        payment.status == PagamentoStatus.PENDENTE.value and payment.provider
        for payment in charge.pagamentos
    ):
        raise financial_service.FinanceiroConflito(
            "Existe uma tentativa externa pendente. Concilie ou cancele antes de registrar o Pix direto."
        )
    balance = financial_service.saldo_pendente(charge)
    if balance <= ZERO:
        raise financial_service.FinanceiroConflito("Cobranca sem saldo pendente.")
    amount = (
        balance
        if dados.modo == "quitar"
        else financial_service.normalizar_valor(dados.valor)
    )
    if dados.modo == "parcial" and amount >= balance:
        raise financial_service.FinanceiroConflito(
            "Para pagar todo o saldo, use a opcao Quitar saldo."
        )
    paid_before = financial_service.valor_pago(charge)
    kind = (
        "integral"
        if not paid_before and amount == balance
        else ("entrada" if not paid_before else "saldo")
    )
    payment = financial_service.registrar_pagamento(
        db,
        charge.id,
        tipo=kind,
        valor=amount,
        status=PagamentoStatus.APROVADO,
        metodo="pix_direto",
        provider="manual_admin",
        provider_reference=dados.referencia,
        provider_idempotency_key=key,
    )
    charge = financial_service.bloquear_cobranca(db, charge.id)
    producao_liberacao_service.avaliar_cobranca_bloqueada(
        db, charge, actor=actor, request_id=request_id
    )
    audit_service.record(
        db,
        actor=actor,
        action="payment.manual_pix_recorded",
        entity_type="payment",
        entity_id=payment.id,
        metadata={"new_status": payment.status, "new_amount": str(amount)},
        request_id=request_id,
    )
    db.commit()
    db.refresh(charge, ["pagamentos"])
    return _manual_response(charge, payment)


def _manual_response(charge, payment, *, repeated=False):
    return {
        "payment_id": payment.id,
        "cobranca_id": charge.id,
        "valor": _money(payment.valor),
        "valor_pago": financial_service.valor_pago(charge),
        "saldo_pendente": financial_service.saldo_pendente(charge),
        "status": charge.status,
        "repeated": repeated,
    }


def anular_pix_manual(db, payment_id, dados, *, actor, request_id=None):
    """AUD6-S10-001: void a direct Pix recorded by mistake, with a reason.

    The charge is recalculated and every release that depends on it is
    re-evaluated (beat licenses are revoked). Effects that cannot be reverted
    automatically are either refused (credits already granted) or returned as
    warnings for the operator (production or payout already released).
    """
    from models import CreditoLoteModel, ProducaoModel
    from models.portal_produtor import RepasseProdutorModel

    payment = db.scalar(
        select(PagamentoModel).where(PagamentoModel.id == payment_id).with_for_update()
    )
    if payment is None:
        raise financial_service.FinanceiroInvalido("Pagamento não encontrado.")
    if payment.provider != "manual_admin":
        raise financial_service.FinanceiroConflito(
            "Somente pagamentos registrados como Pix direto podem ser anulados."
        )
    if payment.status == PagamentoStatus.CANCELADO.value:
        raise financial_service.FinanceiroConflito("Este pagamento já foi anulado.")
    if payment.status != PagamentoStatus.APROVADO.value:
        raise financial_service.FinanceiroConflito("Somente pagamentos aprovados podem ser anulados.")
    charge = financial_service.bloquear_cobranca(db, payment.cobranca_id)
    if charge is None:
        raise financial_service.FinanceiroInvalido("Cobrança não encontrada.")
    if db.scalar(select(CreditoLoteModel.id).where(CreditoLoteModel.cobranca_id == charge.id)):
        raise financial_service.FinanceiroConflito(
            "Esta cobrança já gerou créditos para o cliente; a anulação exige revisão manual dos créditos."
        )
    old_charge_status = charge.status
    payment.status = PagamentoStatus.CANCELADO.value
    payment.reconciliation_status = None
    payment.reconciliation_reason = None
    db.flush()
    db.refresh(charge, ["pagamentos"])
    financial_service.sincronizar_status(charge)
    producao_liberacao_service.avaliar_cobranca_bloqueada(
        db, charge, actor=actor, request_id=request_id
    )
    warnings = []
    production = None
    if charge.proposta is not None:
        production = db.scalar(
            select(ProducaoModel).where(ProducaoModel.orcamento_id == charge.proposta.orcamento_id)
        )
    if production is not None:
        warnings.append(
            f"A produção #{production.id} já foi liberada; revise se ela deve continuar."
        )
        payout = db.scalar(
            select(RepasseProdutorModel).where(RepasseProdutorModel.producao_id == production.id)
        )
        if payout is not None and payout.status in ("liberado", "pago"):
            warnings.append(f"O repasse do produtor já está {payout.status}.")
    audit_service.record(
        db,
        actor=actor,
        action="payment.manual_pix_voided",
        entity_type="payment",
        entity_id=payment.id,
        metadata={
            "old_status": PagamentoStatus.APROVADO.value,
            "new_status": payment.status,
            "amount": str(_money(payment.valor)),
            "charge_old_status": old_charge_status,
            "charge_new_status": charge.status,
            "reason": dados.motivo.strip()[:500],
        },
        request_id=request_id,
    )
    db.commit()
    db.refresh(charge, ["pagamentos"])
    return {
        "payment_id": payment.id,
        "cobranca_id": charge.id,
        "valor": _money(payment.valor),
        "valor_pago": financial_service.valor_pago(charge),
        "saldo_pendente": financial_service.saldo_pendente(charge),
        "status": charge.status,
        "avisos": warnings,
    }
