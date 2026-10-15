"""Contractual portal policies (Roadmap 3.0, 5.10).

Global defaults are append-only versions (like the 5.01 portal settings). A service stores
only the keys it overrides. A production keeps the policies frozen from its contract and,
optionally, an admin exception with its reason.
"""
from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database import Base

_JSON = JSON().with_variant(JSONB(), "postgresql")


class PoliticaGlobalModel(Base):
    __tablename__ = "politicas_globais"
    __table_args__ = (
        CheckConstraint("versao > 0", name="ck_politicas_globais_versao_positiva"),
        UniqueConstraint("versao", name="uq_politicas_globais_versao"),
    )

    id = Column(Integer, primary_key=True)
    versao = Column(Integer, nullable=False)
    dados = Column(_JSON, nullable=False)
    autor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    restaurada_de_versao = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ServicoPoliticaModel(Base):
    __tablename__ = "servico_politicas"

    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="CASCADE"), primary_key=True)
    dados = Column(_JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProducaoPoliticaModel(Base):
    __tablename__ = "producao_politicas"

    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), primary_key=True)
    contrato = Column(_JSON, nullable=True)  # Frozen complete policies; null before 5.10 or without services.
    excecao = Column(_JSON, nullable=True)  # Admin overrides (partial); null = none.
    motivo = Column(String(500), nullable=True)
    atualizado_por_usuario_id = Column(Integer, nullable=True)  # Historical record; no FK on purpose.
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
