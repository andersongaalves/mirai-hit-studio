from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Integer, String, Text

from database import Base


class ProjetoModel(Base):

    __tablename__ = "projetos"

    __table_args__ = (
        CheckConstraint(
            "vertical IS NULL OR vertical IN ('artists', 'creators', 'media_games')",
            name="ck_projetos_vertical_valida",
        ),
        CheckConstraint(
            "case_type IS NULL OR case_type IN ('client_case', 'demo', 'concept_project', 'study')",
            name="ck_projetos_case_type_valido",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    titulo = Column(String(150), nullable=False)

    artista = Column(String(100), nullable=False)

    categoria = Column(String(100), nullable=False)

    link_audio = Column(String(500))

    link_capa = Column(String(500))

    descricao = Column(Text)

    destaque = Column(Boolean, default=False)

    vertical = Column(String(32), nullable=True, index=True)

    segmentos_json = Column(JSON, nullable=False, default=list)

    case_type = Column(String(32), nullable=True, index=True)

    link_audio = Column(String(500), nullable=False)

    link_capa = Column(String(500), nullable=False)
