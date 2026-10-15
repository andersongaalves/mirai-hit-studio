from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from database import Base

STATUS_ETAPA = ("pendente", "em_andamento", "em_revisao", "concluida")


class ProducaoEtapaModel(Base):
    """Contract stage instantiated in a production (Roadmap 3.0, 5.06).

    Created once from the proposal's frozen economic snapshot (5.05). Name, weight, value
    and origin are contract data and never follow later catalog edits; only status,
    deadline and (in 5.07) the responsible person change during the production.
    """

    __tablename__ = "producao_etapas"
    __table_args__ = (
        UniqueConstraint("producao_id", "ordem", name="uq_producao_etapas_producao_ordem"),
        CheckConstraint("ordem > 0 AND ordem_no_item > 0 AND item_indice > 0", name="ck_producao_etapas_ordem"),
        CheckConstraint(
            "status IN ('pendente', 'em_andamento', 'em_revisao', 'concluida')",
            name="ck_producao_etapas_status",
        ),
        CheckConstraint("peso_percentual >= 0 AND peso_percentual <= 100", name="ck_producao_etapas_peso"),
        CheckConstraint("valor >= 0", name="ck_producao_etapas_valor"),
        CheckConstraint(
            "ordem_no_item > 1 OR depende_da_anterior = false",
            name="ck_producao_etapas_primeira_sem_dependencia",
        ),
        CheckConstraint(
            "(status = 'concluida') = (concluida_em IS NOT NULL)",
            name="ck_producao_etapas_conclusao",
        ),
    )

    id = Column(Integer, primary_key=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False, index=True)
    proposta_id = Column(Integer, ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=False)
    item_indice = Column(Integer, nullable=False)
    item_descricao = Column(String(200), nullable=False, default="")
    servico_id = Column(Integer, nullable=True)  # Contract origin only; no FK on purpose.
    ordem = Column(Integer, nullable=False)
    ordem_no_item = Column(Integer, nullable=False)
    nome = Column(String(100), nullable=False)
    peso_percentual = Column(Numeric(5, 2), nullable=False)
    valor = Column(Numeric(12, 2), nullable=False)
    prazo_dias = Column(Integer, nullable=True)
    unidade = Column(String(30), nullable=False, default="")
    revisoes_incluidas = Column(Integer, nullable=True)
    # 5.10: review rounds used (each em_revisao -> em_andamento return counts one).
    revisoes_usadas = Column(Integer, nullable=False, default=0, server_default="0")
    depende_da_anterior = Column(Boolean, nullable=False, default=False)
    administrativa = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="pendente", server_default="pendente")
    prazo = Column(DateTime(timezone=True), nullable=True)
    responsavel_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    # 5.07: who was responsible when the stage was concluded; kept across reassignments.
    # Historical record without a foreign key, so it is never lost (like servico_id).
    executor_usuario_id = Column(Integer, nullable=True)
    iniciada_em = Column(DateTime(timezone=True), nullable=True)
    concluida_em = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class ProducaoEtapaAtribuicaoModel(Base):
    """Append-only history of who is responsible for each contract stage (5.07)."""

    __tablename__ = "producao_etapa_atribuicoes"

    id = Column(Integer, primary_key=True)
    etapa_id = Column(Integer, ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False, index=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False)
    anterior_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    novo_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    atribuido_por_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    motivo = Column(String(300), nullable=False, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
