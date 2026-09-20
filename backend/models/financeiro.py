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
        UniqueConstraint("provider_payment_id", name="uq_pagamentos_provider_payment_id"),
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
    provider_payment_id = Column(String(200), nullable=True)
    provider_reference = Column(String(200), nullable=True)
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
