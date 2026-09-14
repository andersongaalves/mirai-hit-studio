from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


NewsletterStatus = Literal["active", "unsubscribed"]
NewsletterCampaignStatus = Literal["draft", "sending", "sent", "failed"]
NewsletterDeliveryStatus = Literal["pending", "sent", "failed", "skipped"]


class NewsletterSubscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(max_length=150)
    nome: str | None = Field(default=None, max_length=120)
    source: Literal["site_footer", "site_newsletter"] = "site_footer"

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("nome")
    @classmethod
    def normalizar_nome(cls, value: str | None):
        if value is None:
            return None
        value = value.strip()
        return value or None


class NewsletterUnsubscribe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=64)

    @field_validator("token")
    @classmethod
    def token_valido(cls, value: str):
        value = value.strip()
        if len(value) < 20:
            raise ValueError("token_invalido")
        return value


class NewsletterSubscriberDeactivate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ativo: Literal[False]


class NewsletterCampaignCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo_interno: str = Field(min_length=1, max_length=120)
    assunto: str = Field(min_length=1, max_length=160)
    preview_text: str | None = Field(default=None, max_length=200)
    body_text: str = Field(min_length=1, max_length=30_000)

    @field_validator("titulo_interno", "assunto", "body_text")
    @classmethod
    def texto_obrigatorio(cls, value: str):
        value = value.strip()
        if not value:
            raise ValueError("campo_obrigatorio")
        return value

    @field_validator("preview_text")
    @classmethod
    def preview_opcional(cls, value: str | None):
        return value.strip() or None if value is not None else None


class NewsletterCampaignUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    titulo_interno: str | None = Field(default=None, min_length=1, max_length=120)
    assunto: str | None = Field(default=None, min_length=1, max_length=160)
    preview_text: str | None = Field(default=None, max_length=200)
    body_text: str | None = Field(default=None, min_length=1, max_length=30_000)

    @field_validator("titulo_interno", "assunto", "body_text")
    @classmethod
    def texto_atualizavel(cls, value: str | None):
        if value is None:
            raise ValueError("campo_nao_nulo")
        value = value.strip()
        if not value:
            raise ValueError("campo_obrigatorio")
        return value

    @field_validator("preview_text")
    @classmethod
    def preview_atualizavel(cls, value: str | None):
        return value.strip() or None if value is not None else None


class NewsletterSubscriberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nome: str | None
    ativo: bool
    status: NewsletterStatus
    source: str
    consent_at: datetime
    unsubscribed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NewsletterDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subscriber_id: int
    recipient_email: EmailStr
    provider_message_id: str | None
    status: NewsletterDeliveryStatus
    sent_at: datetime | None
    error_summary: str | None
    created_at: datetime


class NewsletterCampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo_interno: str
    assunto: str
    preview_text: str | None
    body_text: str
    status: NewsletterCampaignStatus
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    eligible_subscribers: int = 0
    total_sent: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    deliveries: list[NewsletterDeliveryResponse] = Field(default_factory=list)


NewsletterCreate = NewsletterSubscribe
NewsletterResponse = NewsletterSubscriberResponse
