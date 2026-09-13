from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
from database import get_db
from schemas.newsletter import NewsletterCreate, NewsletterResponse
from services.email_service import EmailService
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])


@router.post("", response_model=NewsletterResponse)
def criar_newsletter(newsletter: NewsletterCreate, db: Session = Depends(get_db)):

    existe = (
        db.query(models.NewsletterModel)
        .filter(models.NewsletterModel.email == newsletter.email)
        .first()
    )

    if existe:

        return existe

    novo = models.NewsletterModel(email=newsletter.email)

    db.add(novo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(models.NewsletterModel).filter(models.NewsletterModel.email == newsletter.email).first()
        if existing:
            return existing
        raise
    db.refresh(novo)

    EmailService.enviar_boas_vindas(novo.email)

    return novo
