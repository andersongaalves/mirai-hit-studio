from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models

from database import get_db

from schemas.newsletter import (
    NewsletterCreate,
    NewsletterResponse
)

from services.email_service import EmailService

router = APIRouter(
    prefix="/newsletter",
    tags=["Newsletter"]
)


@router.post(
    "",
    response_model=NewsletterResponse
)
def criar_newsletter(
    newsletter: NewsletterCreate,
    db: Session = Depends(get_db)
):

    existe = (
        db.query(models.NewsletterModel)
        .filter(
            models.NewsletterModel.email == newsletter.email
        )
        .first()
    )

    if existe:

        raise HTTPException(
            status_code=409,
            detail="Este e-mail já está cadastrado."
        )

    novo = models.NewsletterModel(
        email=newsletter.email
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    EmailService.enviar_boas_vindas(
        novo.email
    )

    return novo