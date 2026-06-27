from sqlalchemy import Column, Integer, Float, String, Text, Boolean
from database import Base

class ServicoModel(Base):
    __tablename__ = "servicos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    subtitulo = Column(String(150), nullable=False, default="")
    valor_base = Column(Float, nullable=False)
    categoria = Column(String(100))
    aplica_desconto = Column(Boolean, default=False)
    parametros = Column(Text)
    descricao_servico = Column(
        Text,
        nullable=False,
        default=""
    )
    estrutura_servico = Column(
        Text,
        nullable=False,
        default="{}"
    )