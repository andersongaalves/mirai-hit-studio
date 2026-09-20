from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base
from models.enums.financeiro import CobrancaStatus, PagamentoStatus


class CobrancaModel(Base):
    __tablename__ = "cobrancas"
    __table_args__ = (
        CheckConstraint("valor_total > 0", name="ck_cobrancas_valor_total_positivo"),
        CheckConstraint("moeda = 'BRL'", name="ck_cobrancas_moeda_brl"),
        CheckConstraint(
            "status IN ('pendente', 'parcialmente_paga', 'paga', 'cancelada')",
            name="ck_cobrancas_status_valido",
        ),
        UniqueConstraint("proposta_id", name="uq_cobrancas_proposta_id"),
        UniqueConstraint("referencia_externa", name="uq_cobrancas_referencia_externa"),
    )

    id = Column(Integer, primary_key=True, index=True)
    proposta_id = Column(Integer, ForeignKey("propostas.id"), nullable=False, index=True)
    cliente_id = Column(
        Integer,
        ForeignKey("clientes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    valor_total = Column(Numeric(12, 2), nullable=False)
    moeda = Column(String(3), default="BRL", nullable=False)
    status = Column(
        String(24),
        default=CobrancaStatus.PENDENTE.value,
        nullable=False,
        index=True,
    )
    vencimento = Column(DateTime(timezone=True), nullable=True)
    referencia_externa = Column(String(36), default=lambda: str(uuid4()), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    proposta = relationship("PropostaModel", back_populates="cobranca")
    cliente = relationship("ClienteModel", back_populates="cobrancas")
    pagamentos = relationship(
        "PagamentoModel",
        back_populates="cobranca",
        cascade="all, delete-orphan",
        order_by="PagamentoModel.id",
    )


class PagamentoModel(Base):
    __tablename__ = "pagamentos"
    __table_args__ = (
        CheckConstraint("valor > 0", name="ck_pagamentos_valor_positivo"),
        CheckConstraint(
            "tipo IN ('integral', 'entrada', 'saldo')",
            name="ck_pagamentos_tipo_valido",
        ),
        CheckConstraint(
            "status IN ('pendente', 'aprovado', 'recusado', 'cancelado', 'reembolsado')",
            name="ck_pagamentos_status_valido",
        ),
        CheckConstraint(
            "reconciliation_status IS NULL OR reconciliation_status IN ('required', 'conflict')",
            name="ck_pagamentos_reconciliation_status_valido",
        ),
        UniqueConstraint("provider_order_id", name="uq_pagamentos_provider_payment_id"),
        UniqueConstraint(
            "provider_idempotency_key",
            name="uq_pagamentos_provider_idempotency_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    cobranca_id = Column(
        Integer,
        ForeignKey("cobrancas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = Column(String(20), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    status = Column(
        String(20),
        default=PagamentoStatus.PENDENTE.value,
        nullable=False,
        index=True,
    )
    metodo = Column(String(30), nullable=True)
    provider = Column(String(50), nullable=True)
    provider_order_id = Column(String(200), nullable=True)
    provider_reference = Column(String(200), nullable=True)
    provider_idempotency_key = Column(String(128), nullable=True)
    reconciliation_status = Column(String(20), nullable=True, index=True)
    reconciliation_reason = Column(String(64), nullable=True)
    aprovado_em = Column(DateTime(timezone=True), nullable=True)
    reembolsado_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    cobranca = relationship("CobrancaModel", back_populates="pagamentos")


class ProviderWebhookEventModel(Base):
    __tablename__ = "provider_webhook_events"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'processed', 'ignored', 'conflict', 'failed')",
            name="ck_provider_webhook_events_status_valido",
        ),
        UniqueConstraint(
            "deduplication_key",
            name="uq_provider_webhook_events_deduplication_key",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    pagamento_id = Column(
        Integer,
        ForeignKey("pagamentos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    resource_id = Column(String(200), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)
    action = Column(String(100), nullable=True)
    provider_event_id = Column(String(200), nullable=True)
    provider_request_id = Column(String(128), nullable=False)
    deduplication_key = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, index=True)
    error_category = Column(String(64), nullable=True)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
