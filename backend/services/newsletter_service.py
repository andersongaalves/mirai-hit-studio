from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crud import crud_newsletter
from models.newsletter import NewsletterCampaignModel, NewsletterModel
from schemas.newsletter import NewsletterCampaignCreate, NewsletterCampaignUpdate, NewsletterSubscribe
from services.email_service import EmailService


class NewsletterNaoEncontrada(Exception):
    pass


class NewsletterConflito(Exception):
    pass


class NewsletterInvalida(Exception):
    pass


def _now():
    return datetime.now(timezone.utc)


def _subscriber(db: Session, subscriber_id: int):
    subscriber = crud_newsletter.buscar_subscriber(db, subscriber_id)
    if not subscriber:
        raise NewsletterNaoEncontrada("Inscrito nao encontrado.")
    return subscriber


def _campaign(db: Session, campaign_id: int, **options):
    campaign = crud_newsletter.buscar_campanha(db, campaign_id, **options)
    if not campaign:
        raise NewsletterNaoEncontrada("Campanha nao encontrada.")
    return campaign


def _campaign_response(db: Session, campaign, *, with_deliveries: bool = False, totals=None, eligible_subscribers=None):
    deliveries = crud_newsletter.entregas_da_campanha(db, campaign.id) if with_deliveries else []
    total_sent, total_failed, total_skipped = totals or (
        sum(delivery.status == "sent" for delivery in deliveries),
        sum(delivery.status == "failed" for delivery in deliveries),
        sum(delivery.status == "skipped" for delivery in deliveries),
    )
    return {
        "id": campaign.id,
        "titulo_interno": campaign.titulo_interno,
        "assunto": campaign.assunto,
        "preview_text": campaign.preview_text,
        "body_text": campaign.body_text,
        "status": campaign.status,
        "created_by_id": campaign.created_by_id,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
        "sent_at": campaign.sent_at,
        "eligible_subscribers": eligible_subscribers if eligible_subscribers is not None else crud_newsletter.contar_subscribers_ativos(db),
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "deliveries": deliveries if with_deliveries else [],
    }


def inscrever(db: Session, dados: NewsletterSubscribe):
    email = str(dados.email)
    existing = crud_newsletter.buscar_subscriber_por_email(db, email)
    now = _now()
    if existing:
        if not existing.ativo:
            existing.ativo = True
            existing.consent_at = now
            existing.unsubscribed_at = None
            existing.origem = dados.source
            if dados.nome:
                existing.nome = dados.nome
            db.commit()
            db.refresh(existing)
        return existing, False
    subscriber = NewsletterModel(
        email=email,
        nome=dados.nome,
        origem=dados.source,
        ativo=True,
        consent_at=now,
    )
    db.add(subscriber)
    try:
        db.commit()
        db.refresh(subscriber)
    except IntegrityError:
        db.rollback()
        existing = crud_newsletter.buscar_subscriber_por_email(db, email)
        if existing:
            return existing, False
        raise
    return subscriber, True


def cancelar_por_token(db: Session, token: str):
    subscriber = crud_newsletter.buscar_subscriber_por_token(db, token)
    if not subscriber:
        raise NewsletterNaoEncontrada("Link de cancelamento invalido.")
    if subscriber.ativo:
        subscriber.ativo = False
        subscriber.unsubscribed_at = _now()
        db.commit()
        db.refresh(subscriber)
    return subscriber


def listar_subscribers(db: Session, busca: str = "", ativo: bool | None = None):
    return crud_newsletter.listar_subscribers(db, busca, ativo)


def cancelar_por_admin(db: Session, subscriber_id: int):
    subscriber = _subscriber(db, subscriber_id)
    if subscriber.ativo:
        subscriber.ativo = False
        subscriber.unsubscribed_at = _now()
        db.commit()
        db.refresh(subscriber)
    return subscriber


def listar_campanhas(db: Session):
    response = []
    eligible_subscribers = crud_newsletter.contar_subscribers_ativos(db)
    for campaign, total_sent, total_failed, total_skipped in crud_newsletter.listar_campanhas(db):
        response.append(_campaign_response(
            db,
            campaign,
            totals=(int(total_sent), int(total_failed), int(total_skipped)),
            eligible_subscribers=eligible_subscribers,
        ))
    return response


def buscar_campanha(db: Session, campaign_id: int):
    return _campaign_response(db, _campaign(db, campaign_id), with_deliveries=True)


def criar_campanha(db: Session, dados: NewsletterCampaignCreate, user):
    campaign = NewsletterCampaignModel(**dados.model_dump(), created_by_id=user.id, status="draft")
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return _campaign_response(db, campaign)


def atualizar_campanha(db: Session, campaign_id: int, dados: NewsletterCampaignUpdate):
    campaign = _campaign(db, campaign_id)
    if campaign.status != "draft":
        raise NewsletterConflito("Campanhas enviadas nao podem ser alteradas.")
    for field, value in dados.model_dump(exclude_unset=True).items():
        setattr(campaign, field, value)
    db.commit()
    db.refresh(campaign)
    return _campaign_response(db, campaign)


def enviar_campanha(db: Session, campaign_id: int):
    campaign = _campaign(db, campaign_id, lock=True)
    if campaign.status != "draft":
        raise NewsletterConflito("Esta campanha ja foi enviada ou esta em processamento.")
    subscribers = crud_newsletter.subscribers_ativos(db)
    if not subscribers:
        raise NewsletterInvalida("Nao ha inscritos ativos para esta campanha.")
    campaign.status = "sending"
    deliveries = crud_newsletter.criar_entregas_sem_commit(db, campaign, subscribers)
    db.commit()

    for delivery in deliveries:
        subscriber = crud_newsletter.buscar_subscriber(db, delivery.subscriber_id)
        if not subscriber or not subscriber.ativo:
            delivery.status = "skipped"
            delivery.error_summary = "subscriber_unsubscribed"
            db.commit()
            continue
        result = EmailService.enviar_newsletter(subscriber, campaign)
        if isinstance(result, dict) and isinstance(result.get("id"), str) and result["id"].strip():
            delivery.status = "sent"
            delivery.provider_message_id = result["id"].strip()
            delivery.sent_at = _now()
        else:
            delivery.status = "failed"
            delivery.error_summary = "provider_unavailable"
        db.commit()

    deliveries = crud_newsletter.entregas_da_campanha(db, campaign.id)
    campaign.status = "sent" if any(delivery.status == "sent" for delivery in deliveries) else "failed"
    campaign.sent_at = _now()
    db.commit()
    db.refresh(campaign)
    return _campaign_response(db, campaign, with_deliveries=True)
