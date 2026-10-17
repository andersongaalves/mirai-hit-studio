from sqlalchemy import JSON, Column, Integer, Float, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from database import Base


class ServicoModel(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    subtitulo = Column(String(150), nullable=False, default="")
    valor_base = Column(Float, nullable=False)
    categoria = Column(String(100))
    aplica_desconto = Column(Boolean, default=False)
    promocao = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=True)
    parametros = Column(Text)
    estrutura_servico = Column(
        Text, nullable=False, default='{"intro":"","sections":[],"benefits":[]}'
    )
    # Roadmap 5.04: catalog stages follow the service; contracts keep their own snapshot.
    etapas = relationship(
        "ServicoEtapaModel",
        cascade="all, delete-orphan",
        order_by="ServicoEtapaModel.ordem",
    )
