from sqlalchemy import Column, Integer, Float, String, Text, DateTime
from sqlalchemy.sql import func

from database import Base


class OrcamentoModel(Base):

    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)

    nome_cliente = Column(String(120), nullable=False)

    email = Column(String(150), nullable=False)

    whatsapp = Column(String(30))

    servico = Column(
        String(100),
        nullable=False
    )

    valor_total = Column(Float)

    link_guia = Column(String(500))

    detalhes = Column(Text)

    data_solicitacao = Column(
        DateTime(timezone=True),
        server_default=func.now()
    )