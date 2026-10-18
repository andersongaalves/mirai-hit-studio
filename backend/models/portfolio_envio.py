"""Private producer submissions; public projects are created only on admin approval."""

from database import Base
from sqlalchemy import (
    DDL,
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
)


class PortfolioEnvioModel(Base):
    __tablename__ = "portfolio_envios"
    __table_args__ = (
        UniqueConstraint("produtor_id", "request_id", name="uq_portfolio_envio_request"),
        CheckConstraint("status IN ('pendente', 'aprovado', 'recusado')", name="ck_portfolio_envio_status"),
        CheckConstraint("versao >= 1", name="ck_portfolio_envio_versao"),
        CheckConstraint("autorizado_em IS NOT NULL", name="ck_portfolio_envio_consentimento"),
    )

    id = Column(Integer, primary_key=True)
    produtor_id = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=True)
    request_id = Column(String(36), nullable=False)
    dados = Column(JSON, nullable=False)
    status = Column(String(12), nullable=False, default="pendente", server_default="pendente")
    versao = Column(Integer, nullable=False, default=1, server_default="1")
    autorizado_em = Column(DateTime(timezone=True), nullable=False)
    revisado_em = Column(DateTime(timezone=True), nullable=True)
    revisado_por = Column(Integer, ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id", ondelete="SET NULL"), nullable=True, unique=True)
    motivo = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


event.listen(PortfolioEnvioModel.__table__, "after_create", DDL(
    "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(PortfolioEnvioModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; "
        "REVOKE ALL ON SEQUENCE public.portfolio_envios_id_seq FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
