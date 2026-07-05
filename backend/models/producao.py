from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey

from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class ProducaoModel(Base):

    __tablename__ = "producoes"

    id = Column(Integer, primary_key=True, index=True)

    titulo = Column(String(150), nullable=False)

    cliente = Column(String(120), nullable=False)

    servico = Column(String(100), nullable=False)

    status = Column(String(30), default="aguardando_inicio")

    produtor_id = Column(Integer, ForeignKey("usuarios.id"))

    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), unique=True)

    observacoes = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    produtor = relationship("UsuarioModel")

    etapas = Column(Text, default="[]", nullable=False)

    prazo_entrega = Column(DateTime(timezone=True), nullable=True)
