from database import Base
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from models.enums.proposta import PoliticaPagamento, PropostaStatus


class PropostaModel(Base):
    __tablename__ = "propostas"
    __table_args__ = (
        CheckConstraint(
            "politica_pagamento IN ('integral', 'entrada_50_50')",
            name="ck_propostas_politica_pagamento_valida",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    orcamento_id = Column(
        Integer,
        ForeignKey("orcamentos.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    numero = Column(
        String(30),
        nullable=False,
        unique=True,
        index=True,
    )

    versao = Column(
        Integer,
        default=1,
        nullable=False,
    )

    status = Column(
        String(20),
        default=PropostaStatus.RASCUNHO.value,
        nullable=False,
    )

    produtor_id = Column(
        Integer,
        ForeignKey("usuarios.id"),
        nullable=True,
    )

    cliente_snapshot = Column(
        JSON,
        nullable=False,
    )

    objeto = Column(
        String(200),
        default="",
        nullable=False,
    )

    descricao = Column(
        Text,
        default="",
        nullable=False,
    )

    itens_json = Column(
        JSON,
        default=list,
        nullable=False,
    )

    pagamentos_json = Column(
        JSON,
        default=list,
        nullable=False,
    )

    politica_pagamento = Column(
        String(20),
        default=PoliticaPagamento.ENTRADA_50_50.value,
        server_default=PoliticaPagamento.ENTRADA_50_50.value,
        nullable=False,
    )

    condicoes = Column(
        Text,
        default="",
        nullable=False,
    )

    totais_json = Column(
        JSON,
        default=dict,
        nullable=False,
    )

    pdf_path = Column(
        String(500),
        nullable=True,
    )

    pdf_sha256 = Column(
        String(64),
        nullable=True,
    )

    gerada_em = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    enviada_em = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    aprovada_em = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    orcamento = relationship(
        "OrcamentoModel",
        back_populates="proposta",
    )

    produtor = relationship(
        "UsuarioModel",
        foreign_keys=[produtor_id],
    )

    cobranca = relationship(
        "CobrancaModel",
        back_populates="proposta",
        uselist=False,
        cascade="all, delete-orphan",
    )
