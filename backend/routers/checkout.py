from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from core.dependencies import get_current_user
from database import get_db
from integrations.mercado_pago import MercadoPagoClient, MercadoPagoError, MercadoPagoNotConfigured
from schemas.checkout import (
    CheckoutCardRequest,
    CheckoutConfig,
    CheckoutLinkResponse,
    CheckoutPaymentRequest,
    CheckoutPaymentResponse,
    CheckoutStatus,
    CheckoutSummary,
)
from services import checkout_service


router = APIRouter(prefix="/checkout", tags=["Checkout"])
Token = Annotated[str, Path(min_length=36, max_length=36)]


def get_mercado_pago_client():
    return MercadoPagoClient()


def _execute(callback):
    try:
        return callback()
    except checkout_service.CheckoutNaoEncontrado as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
    except checkout_service.CheckoutIndisponivel as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except checkout_service.CheckoutConflito as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    except MercadoPagoNotConfigured:
        raise HTTPException(status_code=503, detail="Pagamento temporariamente indisponivel.") from None
    except MercadoPagoError as error:
        status = 429 if error.http_status == 429 else 503
        raise HTTPException(status_code=status, detail="Provider de pagamento temporariamente indisponivel.") from None
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Checkout temporariamente indisponivel.") from None


@router.get("/config", response_model=CheckoutConfig)
def config():
    key = settings.MERCADO_PAGO_PUBLIC_KEY
    if not isinstance(key, str) or not key.strip():
        raise HTTPException(status_code=503, detail="Pagamento por cartao indisponivel.")
    return CheckoutConfig(mercado_pago_public_key=key.strip())


@router.get("/proposta/{proposta_id}/link", response_model=CheckoutLinkResponse)
def link(
    proposta_id: Annotated[int, Path(gt=0)],
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    base_url = getattr(settings, "PUBLIC_FRONTEND_URL", "http://localhost:4173")
    return CheckoutLinkResponse(
        checkout_url=_execute(
            lambda: checkout_service.link_por_proposta(db, proposta_id, base_url)
        )
    )


@router.get("/{token}", response_model=CheckoutSummary)
def summary(token: Token, db: Session = Depends(get_db)):
    return _execute(lambda: checkout_service.resumo(db, token))


@router.get("/{token}/status", response_model=CheckoutStatus)
def payment_status(token: Token, db: Session = Depends(get_db)):
    return _execute(lambda: checkout_service.status(db, token))


@router.get("/{token}/pending-payment", response_model=CheckoutPaymentResponse)
def pending_payment(
    token: Token,
    request: Request,
    db: Session = Depends(get_db),
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    return _execute(
        lambda: checkout_service.recuperar(
            db, token, client=client, request_id=request.state.request_id
        )
    )


@router.post("/{token}/pix", response_model=CheckoutPaymentResponse)
def pix(
    token: Token,
    dados: CheckoutPaymentRequest,
    request: Request,
    db: Session = Depends(get_db),
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    return _execute(
        lambda: checkout_service.criar_pix(
            db,
            token,
            dados.payment_option,
            client=client,
            request_id=request.state.request_id,
        )
    )


@router.post("/{token}/card", response_model=CheckoutPaymentResponse)
def card(
    token: Token,
    dados: CheckoutCardRequest,
    request: Request,
    db: Session = Depends(get_db),
    client: MercadoPagoClient = Depends(get_mercado_pago_client),
):
    return _execute(
        lambda: checkout_service.criar_cartao(
            db, token, dados, client=client, request_id=request.state.request_id
        )
    )
