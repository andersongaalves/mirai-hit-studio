from database import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)

from models.carteira_creditos import proteger_registro


class RepasseEtapaModel(Base):
    __tablename__ = "repasse_etapas"
    __table_args__ = (
        CheckConstraint("bruto_centavos > 0 AND produtor_centavos >= 0 AND mirai_centavos >= 0 "
                        "AND produtor_centavos + mirai_centavos = bruto_centavos", name="ck_repasse_etapa_centavos"),
    )
    id = Column(Integer, primary_key=True)
    etapa_id = Column(Integer, ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False, index=True)
    produtor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    bruto_centavos = Column(Integer, nullable=False)
    produtor_centavos = Column(Integer, nullable=False)
    mirai_centavos = Column(Integer, nullable=False)
    origem_sha256 = Column(String(64), nullable=False)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class RepasseEtapaPagamentoModel(Base):
    __tablename__ = "repasse_etapa_pagamentos"
    id = Column(Integer, primary_key=True)
    repasse_id = Column(Integer, ForeignKey("repasse_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True)
    referencia = Column(String(160), nullable=False)
    comprovante_arquivo_id = Column(Integer, ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), nullable=True, unique=True)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    idempotency_key = Column(String(36), nullable=False, unique=True)
    request_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


for model in (RepasseEtapaModel, RepasseEtapaPagamentoModel):
    proteger_registro(model)
