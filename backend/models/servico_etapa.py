from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, Numeric, String, UniqueConstraint

from database import Base


class ServicoEtapaModel(Base):
    """Catalog stages of a service with percentage weights (Roadmap 5.04).

    The catalog is a template: contracts and productions must snapshot these values
    (5.05/5.06), so later catalog edits never rewrite existing work.
    """

    __tablename__ = "servico_etapas"
    __table_args__ = (
        UniqueConstraint("servico_id", "ordem", name="uq_servico_etapas_servico_ordem"),
        CheckConstraint("ordem > 0", name="ck_servico_etapas_ordem_positiva"),
        CheckConstraint("peso_percentual >= 0 AND peso_percentual <= 100", name="ck_servico_etapas_peso"),
        CheckConstraint("prazo_dias IS NULL OR (prazo_dias >= 0 AND prazo_dias <= 365)", name="ck_servico_etapas_prazo"),
        CheckConstraint(
            "revisoes_incluidas IS NULL OR (revisoes_incluidas >= 0 AND revisoes_incluidas <= 20)",
            name="ck_servico_etapas_revisoes",
        ),
        CheckConstraint("ordem > 1 OR depende_da_anterior = false", name="ck_servico_etapas_primeira_sem_dependencia"),
    )

    id = Column(Integer, primary_key=True)
    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="CASCADE"), nullable=False, index=True)
    ordem = Column(Integer, nullable=False)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(300), nullable=False, default="")
    peso_percentual = Column(Numeric(5, 2), nullable=False)
    prazo_dias = Column(Integer, nullable=True)
    unidade = Column(String(30), nullable=False, default="")
    revisoes_incluidas = Column(Integer, nullable=True)
    depende_da_anterior = Column(Boolean, nullable=False, default=False)
    administrativa = Column(Boolean, nullable=False, default=False)
