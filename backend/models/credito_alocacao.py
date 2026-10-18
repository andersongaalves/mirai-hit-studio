from database import Base
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)

from models.carteira_creditos import proteger_registro


class CreditoAlocacaoModel(Base):
    __tablename__ = "credito_alocacoes"
    __table_args__ = (
        CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_alocacao_quantidade"),
        CheckConstraint("valor_centavos >= 0", name="ck_credito_alocacao_valor"),
        CheckConstraint("length(motivo) >= 5", name="ck_credito_alocacao_motivo"),
    )
    id = Column(Integer, primary_key=True)
    lote_id = Column(Integer, ForeignKey("credito_lotes.id", ondelete="RESTRICT"), nullable=False, index=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False)
    quantidade = Column(Numeric(12, 3), nullable=False)
    valor_centavos = Column(Integer, nullable=False)
    snapshot_servico = Column(JSON, nullable=False)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    motivo = Column(String(500), nullable=False)
    idempotency_key = Column(String(36), nullable=False, unique=True)
    request_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CreditoMovimentoModel(Base):
    __tablename__ = "credito_movimentos"
    __table_args__ = (
        UniqueConstraint("alocacao_id", "tipo", name="uq_credito_movimento_tipo"),
        CheckConstraint("tipo IN ('reserva','consumo','devolucao','estorno')", name="ck_credito_movimento_tipo"),
        CheckConstraint("length(motivo) >= 5", name="ck_credito_movimento_motivo"),
    )
    id = Column(Integer, primary_key=True)
    alocacao_id = Column(Integer, ForeignKey("credito_alocacoes.id", ondelete="RESTRICT"), nullable=False)
    tipo = Column(String(12), nullable=False)
    autor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False)
    motivo = Column(String(500), nullable=False)
    idempotency_key = Column(String(36), nullable=False, unique=True)
    request_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


for model in (CreditoAlocacaoModel, CreditoMovimentoModel):
    proteger_registro(model)
