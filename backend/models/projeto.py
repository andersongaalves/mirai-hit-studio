from sqlalchemy import Column, Integer, String, Text, Boolean

from database import Base


class ProjetoModel(Base):

    __tablename__ = "projetos"

    id = Column(Integer, primary_key=True, index=True)

    titulo = Column(String(150), nullable=False)

    artista = Column(String(100), nullable=False)

    categoria = Column(String(100), nullable=False)

    link_audio = Column(String(500))

    link_capa = Column(String(500))

    descricao = Column(Text)

    destaque = Column(Boolean, default=False)

    link_audio = Column(
        String(500),
        nullable=False
    )

    link_capa = Column(
        String(500),
        nullable=False
    )