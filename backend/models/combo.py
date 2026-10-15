from sqlalchemy import (
    JSON,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false, func

from database import Base


class ComboModel(Base):
    """Catalog combo of services (Roadmap 3.0, 5.08).

    The base price is a reference; proposals still negotiate the line value. When a
    proposal is sent, the contracted value is split first among the component services
    and then among each service's stages (two-level distribution, 5.05 snapshot).
    """

    __tablename__ = "combos"
    __table_args__ = (CheckConstraint("preco_base >= 0", name="ck_combos_preco_base"),)

    id = Column(Integer, primary_key=True)
    nome = Column(String(100), nullable=False)
    descricao = Column(String(1000), nullable=False, default="")
    preco_base = Column(Numeric(12, 2), nullable=False)
    ativo = Column(Boolean, nullable=False, default=True)
    # Catalog rework: a combo is sold like a service; limits, stages and quotas come from its services.
    subtitulo = Column(String(150), nullable=False, default="", server_default="")
    aplica_desconto = Column(Boolean, nullable=False, default=False, server_default=false())
    destaques = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    itens = relationship(
        "ComboItemModel",
        cascade="all, delete-orphan",
        order_by="ComboItemModel.ordem",
    )


class ComboItemModel(Base):
    __tablename__ = "combo_itens"
    __table_args__ = (
        UniqueConstraint("combo_id", "servico_id", name="uq_combo_itens_combo_servico"),
        UniqueConstraint("combo_id", "ordem", name="uq_combo_itens_combo_ordem"),
        CheckConstraint("ordem > 0", name="ck_combo_itens_ordem"),
    )

    id = Column(Integer, primary_key=True)
    combo_id = Column(Integer, ForeignKey("combos.id", ondelete="CASCADE"), nullable=False, index=True)
    servico_id = Column(Integer, ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False)
    ordem = Column(Integer, nullable=False)

    servico = relationship("ServicoModel")
