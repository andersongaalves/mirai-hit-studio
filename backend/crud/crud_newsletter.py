from sqlalchemy import case, func
from sqlalchemy.orm import Session

from models.newsletter import NewsletterCampaignModel, NewsletterDeliveryModel, NewsletterModel


def buscar_subscriber_por_email(db: Session, email: str):
    return db.query(NewsletterModel).filter(NewsletterModel.email == email).first()


def buscar_subscriber_por_token(db: Session, token: str):
    return db.query(NewsletterModel).filter(NewsletterModel.unsubscribe_token == token).first()


def buscar_subscriber(db: Session, subscriber_id: int):
    return db.get(NewsletterModel, subscriber_id)


def listar_subscribers(db: Session, busca: str = "", ativo: bool | None = None):
    query = db.query(NewsletterModel)
    if busca:
        query = query.filter(func.lower(NewsletterModel.email).like(f"%{busca.lower()}%"))
    if ativo is not None:
        query = query.filter(NewsletterModel.ativo.is_(ativo))
    return query.order_by(NewsletterModel.data_cadastro.desc(), NewsletterModel.id.desc()).all()


def subscribers_ativos(db: Session):
    return db.query(NewsletterModel).filter(NewsletterModel.ativo.is_(True)).all()


def contar_subscribers_ativos(db: Session):
    return db.query(func.count(NewsletterModel.id)).filter(NewsletterModel.ativo.is_(True)).scalar() or 0


def buscar_campanha(db: Session, campaign_id: int, *, lock: bool = False):
    query = db.query(NewsletterCampaignModel).filter(NewsletterCampaignModel.id == campaign_id)
    if lock:
        query = query.with_for_update()
    return query.first()


def listar_campanhas(db: Session):
    sent = func.coalesce(func.sum(case((NewsletterDeliveryModel.status == "sent", 1), else_=0)), 0)
    failed = func.coalesce(func.sum(case((NewsletterDeliveryModel.status == "failed", 1), else_=0)), 0)
    skipped = func.coalesce(func.sum(case((NewsletterDeliveryModel.status == "skipped", 1), else_=0)), 0)
    return (
        db.query(NewsletterCampaignModel, sent.label("total_sent"), failed.label("total_failed"), skipped.label("total_skipped"))
        .outerjoin(NewsletterDeliveryModel, NewsletterDeliveryModel.campaign_id == NewsletterCampaignModel.id)
        .group_by(NewsletterCampaignModel.id)
        .order_by(NewsletterCampaignModel.created_at.desc(), NewsletterCampaignModel.id.desc())
        .all()
    )


def criar_entregas_sem_commit(db: Session, campaign, subscribers):
    deliveries = [
        NewsletterDeliveryModel(
            campaign_id=campaign.id,
            subscriber_id=subscriber.id,
            recipient_email=subscriber.email,
            status="pending",
        )
        for subscriber in subscribers
    ]
    db.add_all(deliveries)
    db.flush()
    return deliveries


def entregas_da_campanha(db: Session, campaign_id: int):
    return (
        db.query(NewsletterDeliveryModel)
        .filter(NewsletterDeliveryModel.campaign_id == campaign_id)
        .order_by(NewsletterDeliveryModel.id.asc())
        .all()
    )
