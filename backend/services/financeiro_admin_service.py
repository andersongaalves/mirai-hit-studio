from datetime import datetime
from decimal import Decimal
from math import ceil

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from core.config import settings
from models.cliente import ClienteModel
from models.enums.financeiro import CobrancaStatus, PagamentoStatus
from models.financeiro import CobrancaModel, PagamentoModel
from models.proposta import PropostaModel
from services import checkout_service, financial_service


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


def resumo(db: Session):
    paid = _paid_subquery()
    saldo = CobrancaModel.valor_total - func.coalesce(paid.c.valor_pago, 0)
    valor_a_receber = db.scalar(
        select(func.coalesce(func.sum(saldo), 0))
        .select_from(CobrancaModel)
        .outerjoin(paid, paid.c.cobranca_id == CobrancaModel.id)
        .where(CobrancaModel.status != CobrancaStatus.CANCELADA.value)
    )
    valor_recebido = db.scalar(
        select(func.coalesce(func.sum(PagamentoModel.valor), 0)).where(
            PagamentoModel.status == PagamentoStatus.APROVADO.value
        )
    )
    return {
        "valor_a_receber": _money(valor_a_receber),
        "valor_recebido": _money(valor_recebido),
        "cobrancas_parciais": db.scalar(
            select(func.count()).select_from(CobrancaModel).where(
                CobrancaModel.status == CobrancaStatus.PARCIALMENTE_PAGA.value
            )
        ) or 0,
        "pagamentos_em_atencao": db.scalar(
            select(func.count()).select_from(PagamentoModel).where(
                PagamentoModel.reconciliation_status.isnot(None)
            )
        ) or 0,
        "total_cobrancas": db.scalar(select(func.count()).select_from(CobrancaModel)) or 0,
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
    search: str | None = None,
    status: str | None = None,
    reconciliation_status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    query = _filters(
        _base_query(),
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
