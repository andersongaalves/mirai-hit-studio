"""File quotas per contract (Roadmap 3.0, 5.09).

The catalog defines quotas per service and file type; they are frozen in the proposal
snapshot (5.05) and become the production's quotas when it is created. Only client and
producer uploads are limited; the admin is the authority and may adjust a production.
"""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database import Base

COTA_TIPOS = ("material", "referencia", "previa", "entrega")
_TIPO_CHECK = "tipo IN ('material', 'referencia', 'previa', 'entrega')"
_LIMITES_CHECK = (
    "(max_arquivos IS NULL OR max_arquivos BETWEEN 1 AND 100)"
    " AND (max_versoes IS NULL OR max_versoes BETWEEN 1 AND 50)"
    " AND (max_tamanho_mb IS NULL OR max_tamanho_mb BETWEEN 1 AND 50)"
    " AND (max_total_mb IS NULL OR max_total_mb BETWEEN 1 AND 5000)"
)


class ServicoCotaArquivoModel(Base):
    __tablename__ = "servico_cotas_arquivo"
    __table_args__ = (
        UniqueConstraint("servico_id", "tipo", name="uq_servico_cotas_arquivo_servico_tipo"),
        CheckConstraint(_TIPO_CHECK, name="ck_servico_cotas_arquivo_tipo"),
        CheckConstraint(_LIMITES_CHECK, name="ck_servico_cotas_arquivo_limites"),
    )

    id = Column(Integer, primary_key=True)
    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    max_arquivos = Column(Integer, nullable=True)
    max_versoes = Column(Integer, nullable=True)
    max_tamanho_mb = Column(Integer, nullable=True)
    max_total_mb = Column(Integer, nullable=True)
    formatos = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)  # MIME list; null = all allowed.


class ProducaoCotaArquivoModel(Base):
    __tablename__ = "producao_cotas_arquivo"
    __table_args__ = (
        UniqueConstraint("producao_id", "tipo", name="uq_producao_cotas_arquivo_producao_tipo"),
        CheckConstraint(_TIPO_CHECK, name="ck_producao_cotas_arquivo_tipo"),
        CheckConstraint(_LIMITES_CHECK, name="ck_producao_cotas_arquivo_limites"),
        CheckConstraint("origem IN ('contrato', 'admin')", name="ck_producao_cotas_arquivo_origem"),
    )

    id = Column(Integer, primary_key=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    max_arquivos = Column(Integer, nullable=True)
    max_versoes = Column(Integer, nullable=True)
    max_tamanho_mb = Column(Integer, nullable=True)
    max_total_mb = Column(Integer, nullable=True)
    formatos = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    origem = Column(String(20), nullable=False, default="contrato")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
