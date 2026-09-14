import secrets

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class NewsletterModel(Base):

    __tablename__ = "newsletter"
    __table_args__ = (
        UniqueConstraint("unsubscribe_token", name="uq_newsletter_unsubscribe_token"),
    )

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(150), unique=True, nullable=False, index=True)

    nome = Column(String(120), nullable=True)

    ativo = Column(Boolean, default=True, nullable=False)

    origem = Column(String(50), default="Footer", nullable=False)

    data_cadastro = Column(DateTime(timezone=True), server_default=func.now())

    consent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    unsubscribed_at = Column(DateTime(timezone=True), nullable=True)

    unsubscribe_token = Column(
        String(64),
        nullable=False,
        default=lambda: secrets.token_urlsafe(32),
    )

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    entregas = relationship("NewsletterDeliveryModel", back_populates="subscriber")

    @property
    def status(self):
        return "active" if self.ativo else "unsubscribed"

    @property
    def source(self):
        return self.origem

    @property
    def created_at(self):
        return self.data_cadastro


class NewsletterCampaignModel(Base):
    __tablename__ = "newsletter_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    titulo_interno = Column(String(120), nullable=False)
    assunto = Column(String(160), nullable=False)
    preview_text = Column(String(200), nullable=True)
    body_text = Column(Text, nullable=False)
    status = Column(String(20), default="draft", nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)

    entregas = relationship("NewsletterDeliveryModel", back_populates="campaign")


class NewsletterDeliveryModel(Base):
    __tablename__ = "newsletter_deliveries"
    __table_args__ = (
        UniqueConstraint("campaign_id", "subscriber_id", name="uq_newsletter_delivery_campaign_subscriber"),
    )

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("newsletter_campaigns.id"), nullable=False, index=True)
    subscriber_id = Column(Integer, ForeignKey("newsletter.id"), nullable=False, index=True)
    recipient_email = Column(String(150), nullable=False)
    provider_message_id = Column(String(120), nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    error_summary = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    campaign = relationship("NewsletterCampaignModel", back_populates="entregas")
    subscriber = relationship("NewsletterModel", back_populates="entregas")
