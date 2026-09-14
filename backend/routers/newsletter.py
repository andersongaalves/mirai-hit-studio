from html import escape

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from core.dependencies import require_admin
from database import get_db
from schemas.newsletter import (
    NewsletterCampaignCreate,
    NewsletterCampaignResponse,
    NewsletterCampaignUpdate,
    NewsletterSubscribe,
    NewsletterSubscriberDeactivate,
    NewsletterSubscriberResponse,
    NewsletterUnsubscribe,
)
from services import newsletter_service


router = APIRouter(prefix="/newsletter", tags=["Newsletter"])


def _erro(error):
    if isinstance(error, newsletter_service.NewsletterNaoEncontrada):
        raise HTTPException(status_code=404, detail=str(error)) from None
    if isinstance(error, newsletter_service.NewsletterConflito):
        raise HTTPException(status_code=409, detail=str(error)) from None
    if isinstance(error, newsletter_service.NewsletterInvalida):
        raise HTTPException(status_code=422, detail=str(error)) from None
    raise error


@router.post("", response_model=NewsletterSubscriberResponse)
@router.post("/subscribe", response_model=NewsletterSubscriberResponse)
def inscrever(dados: NewsletterSubscribe, db: Session = Depends(get_db)):
    subscriber, created = newsletter_service.inscrever(db, dados)
    if created:
        newsletter_service.EmailService.enviar_boas_vindas(subscriber)
    return subscriber


@router.get("/unsubscribe", response_class=HTMLResponse)
def pagina_cancelamento(token: str = Query(min_length=20, max_length=64)):
    safe_token = escape(token, quote=True)
    return HTMLResponse(
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Mirai Hit Studio</title>"
        "<body><main><h1>Cancelar inscrição</h1><p>Confirme o cancelamento das novidades da Mirai Hit Studio.</p>"
        f"<form method='post' action='/newsletter/unsubscribe/confirm'><input type='hidden' name='token' value='{safe_token}'>"
        "<button type='submit'>Cancelar inscrição</button></form></main></body></html>"
    )


@router.post("/unsubscribe", response_model=NewsletterSubscriberResponse)
def cancelar(dados: NewsletterUnsubscribe, db: Session = Depends(get_db)):
    try:
        return newsletter_service.cancelar_por_token(db, dados.token)
    except Exception as error:
        _erro(error)


@router.post("/unsubscribe/confirm", response_class=HTMLResponse)
def confirmar_cancelamento(token: str = Form(min_length=20, max_length=64), db: Session = Depends(get_db)):
    try:
        newsletter_service.cancelar_por_token(db, token)
    except Exception as error:
        _erro(error)
    return HTMLResponse(
        "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Mirai Hit Studio</title>"
        "<body><main><h1>Inscrição cancelada</h1><p>Você não receberá mais newsletters da Mirai Hit Studio.</p></main></body></html>"
    )


@router.get("/subscribers", response_model=list[NewsletterSubscriberResponse])
def listar_subscribers(
    busca: str = Query(default="", max_length=150),
    ativo: bool | None = None,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return newsletter_service.listar_subscribers(db, busca.strip(), ativo)


@router.patch("/subscribers/{subscriber_id}", response_model=NewsletterSubscriberResponse)
def cancelar_subscriber(
    subscriber_id: int,
    dados: NewsletterSubscriberDeactivate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return newsletter_service.cancelar_por_admin(db, subscriber_id)
    except Exception as error:
        _erro(error)


@router.get("/campaigns", response_model=list[NewsletterCampaignResponse])
def listar_campanhas(db: Session = Depends(get_db), user=Depends(require_admin)):
    return newsletter_service.listar_campanhas(db)


@router.get("/campaigns/{campaign_id}", response_model=NewsletterCampaignResponse)
def buscar_campanha(campaign_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    try:
        return newsletter_service.buscar_campanha(db, campaign_id)
    except Exception as error:
        _erro(error)


@router.post("/campaigns", response_model=NewsletterCampaignResponse, status_code=201)
def criar_campanha(
    dados: NewsletterCampaignCreate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    return newsletter_service.criar_campanha(db, dados, user)


@router.patch("/campaigns/{campaign_id}", response_model=NewsletterCampaignResponse)
def atualizar_campanha(
    campaign_id: int,
    dados: NewsletterCampaignUpdate,
    db: Session = Depends(get_db),
    user=Depends(require_admin),
):
    try:
        return newsletter_service.atualizar_campanha(db, campaign_id, dados)
    except Exception as error:
        _erro(error)


@router.post("/campaigns/{campaign_id}/send", response_model=NewsletterCampaignResponse)
def enviar_campanha(campaign_id: int, db: Session = Depends(get_db), user=Depends(require_admin)):
    try:
        return newsletter_service.enviar_campanha(db, campaign_id)
    except Exception as error:
        _erro(error)
