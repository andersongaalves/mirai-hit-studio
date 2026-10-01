from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Index,
    Integer,
    String,
    Text,
    text,
)

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
        CheckConstraint(
            "NOT show_mix_comparison_on_landing OR "
            "(audio_before_key IS NOT NULL AND audio_after_key IS NOT NULL "
            "AND landing_order BETWEEN 1 AND 4)",
            name="ck_projetos_mix_comparison_destaque_valido",
        ),
        CheckConstraint(
            "show_mix_comparison_on_landing OR landing_order IS NULL",
            name="ck_projetos_mix_comparison_order_valida",
        ),
        Index(
            "uq_projetos_mix_comparison_landing_order",
            "landing_order",
            unique=True,
            postgresql_where=text("show_mix_comparison_on_landing"),
            sqlite_where=text("show_mix_comparison_on_landing = 1"),
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    titulo = Column(String(150), nullable=False)

    artista = Column(String(100), nullable=False)

    categoria = Column(String(100), nullable=False)

    descricao = Column(Text)

    destaque = Column(Boolean, default=False)

    vertical = Column(String(32), nullable=True, index=True)

    segmentos_json = Column(JSON, nullable=False, default=list)

    case_type = Column(String(32), nullable=True, index=True)

    audio_before_key = Column(String(500), nullable=True)

    audio_after_key = Column(String(500), nullable=True)

    show_mix_comparison_on_landing = Column(Boolean, nullable=False, default=False)

    landing_order = Column(Integer, nullable=True)

    link_audio = Column(String(500), nullable=False)

    link_capa = Column(String(500), nullable=False)
