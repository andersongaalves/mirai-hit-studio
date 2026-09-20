from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ClienteModel(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False, index=True)
    email = Column(String(150), nullable=True, index=True)
    telefone = Column(String(30), nullable=True, index=True)
    observacoes = Column(Text, default="", nullable=False)
    ativo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    orcamentos = relationship("OrcamentoModel", back_populates="cliente")
    cobrancas = relationship("CobrancaModel", back_populates="cliente")
