from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class OrcamentoModel(Base):

    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)

    nome_cliente = Column(String(120), nullable=False)

    email = Column(String(150), nullable=False)

    whatsapp = Column(String(30))

    servico = Column(String(100), nullable=False)

    valor_total = Column(Float)

    link_guia = Column(String(500))

    detalhes = Column(Text)

    data_solicitacao = Column(DateTime(timezone=True), server_default=func.now())

    status = Column(String(20), default="novo", nullable=False)

    produtor_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    observacoes = Column(Text, default="", nullable=False)

    proposta = relationship(
        "PropostaModel",
        back_populates="orcamento",
        uselist=False,
        cascade="all, delete-orphan",
    )

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    produtor = relationship("UsuarioModel", foreign_keys=[produtor_id])
