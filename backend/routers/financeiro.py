from datetime import datetime
import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from integrations.mercado_pago import MercadoPagoError, MercadoPagoNotConfigured
from models.enums.financeiro import CobrancaStatus
from schemas.financeiro_admin import (
    FinanceiroCobrancaDetalhe,
    FinanceiroCobrancaPage,
    FinanceiroReconciliacaoResponse,
    FinanceiroResumo,
)
from services import audit_service, financial_service, financeiro_admin_service, mercado_pago_service


router = APIRouter(
    prefix="/financeiro",
    tags=["Financeiro"],
    dependencies=[Depends(require_admin)],
)
logger = logging.getLogger(__name__)


@router.get("/resumo", response_model=FinanceiroResumo)
def obter_resumo(db: Session = Depends(get_db)):
    return financeiro_admin_service.resumo(db)


@router.get("/cobrancas", response_model=FinanceiroCobrancaPage)
def listar_cobrancas(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
    search: Annotated[str | None, Query(max_length=120)] = None,
    status: CobrancaStatus | None = None,
    reconciliation_status: Literal["required", "conflict", "clear"] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="Período inválido.")
    return financeiro_admin_service.listar(
        db,
        page=page,
        page_size=page_size,
        search=search,
        status=status.value if status else None,
        reconciliation_status=reconciliation_status,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/cobrancas/{cobranca_id}", response_model=FinanceiroCobrancaDetalhe)
def obter_cobranca(
    cobranca_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
):
    cobranca = financeiro_admin_service.buscar(db, cobranca_id)
    if cobranca is None:
        raise HTTPException(status_code=404, detail="Cobrança não encontrada.")
    return cobranca


@router.post(
    "/pagamentos/{payment_id}/reconciliar",
    response_model=FinanceiroReconciliacaoResponse,
)
def conciliar_pagamento(
    payment_id: Annotated[int, Path(gt=0)],
    request: Request,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    request_id = getattr(request.state, "request_id", None)
    try:
        result = mercado_pago_service.reconcile_payment(
            db, payment_id, request_id=request_id
        )
    except financial_service.FinanceiroInvalido as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except mercado_pago_service.ReconciliationRequired:
        _audit(db, user, "payment.reconciliation_required", payment_id, request_id)
        raise HTTPException(status_code=409, detail="Pagamento requer identificação da ordem no provedor.") from None
    except mercado_pago_service.ReconciliationConflict:
        _audit(db, user, "payment.reconciliation_conflict", payment_id, request_id)
        raise HTTPException(status_code=409, detail="Conciliação encontrou divergência. Revise os dados do pagamento.") from None
    except MercadoPagoNotConfigured:
        raise HTTPException(status_code=503, detail="Provider de pagamento não configurado.") from None
    except MercadoPagoError as error:
        status = 429 if error.http_status == 429 else 503
        raise HTTPException(status_code=status, detail="Provider de pagamento temporariamente indisponível.") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Conciliação temporariamente indisponível.") from None

    _audit(
        db,
        user,
        "payment.reconciled",
        payment_id,
        request_id,
        {"old_status": result.previous_status, "new_status": result.current_status},
    )
    return {
        "payment_id": result.payment_id,
        "previous_status": result.previous_status,
        "current_status": result.current_status,
        "changed": result.changed,
        "outcome": result.outcome,
    }


def _audit(db, user, action, payment_id, request_id, metadata=None):
    try:
        audit_service.record(
            db,
            actor=user,
            action=action,
            entity_type="payment",
            entity_id=payment_id,
            metadata=metadata,
            request_id=request_id,
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "financial_audit_failed action=%s payment_id=%s request_id=%s",
            action,
            payment_id,
            request_id,
        )
