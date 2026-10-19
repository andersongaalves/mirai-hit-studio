from database import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    UniqueConstraint,
    select,
)

from models.carteira_creditos import proteger_registro
from models.credito_alocacao import CreditoMovimentoModel


class CreditoEtapaModel(Base):
    __tablename__ = "credito_etapas"
    __table_args__ = (
        UniqueConstraint("alocacao_id", "ordem_no_item", name="uq_credito_etapa_origem"),
        CheckConstraint("ordem_no_item > 0", name="ck_credito_etapa_ordem"),
    )
    id = Column(Integer, primary_key=True)
    etapa_id = Column(Integer, ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True)
    alocacao_id = Column(Integer, ForeignKey("credito_alocacoes.id", ondelete="RESTRICT"), nullable=False, index=True)
    ordem_no_item = Column(Integer, nullable=False)


proteger_registro(CreditoEtapaModel)


def etapa_ativa(etapa_id):
    terminal = select(CreditoMovimentoModel.id).where(
        CreditoMovimentoModel.alocacao_id == CreditoEtapaModel.alocacao_id,
        CreditoMovimentoModel.tipo.in_(["devolucao", "estorno"]),
    ).exists()
    return ~select(CreditoEtapaModel.id).where(CreditoEtapaModel.etapa_id == etapa_id, terminal).exists()
