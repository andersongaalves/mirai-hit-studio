from database import Base
from sqlalchemy import (
    DDL,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    event,
    func,
)


class PortalNotificacaoModel(Base):
    __tablename__ = "portal_notificacoes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave_evento", name="uq_portal_notificacao_usuario_evento"),
        CheckConstraint("papel IN ('cliente', 'produtor', 'admin')", name="ck_portal_notificacao_papel"),
        CheckConstraint(
            "producao_id IS NOT NULL OR proposta_id IS NOT NULL OR beat_id IS NOT NULL "
            "OR orcamento_id IS NOT NULL OR portfolio_envio_id IS NOT NULL",
            name="ck_portal_notificacao_contexto",
        ),
        Index("ix_portal_notificacao_usuario_vista_id", "usuario_id", "vista_em", "id"),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    papel = Column(String(10), nullable=False)
    chave_evento = Column(String(180), nullable=False)
    tipo = Column(String(40), nullable=False)
    producao_id = Column(Integer, ForeignKey("producoes.id", ondelete="CASCADE"), nullable=True)
    proposta_id = Column(Integer, ForeignKey("propostas.id", ondelete="CASCADE"), nullable=True)
    arquivo_id = Column(Integer, ForeignKey("producao_arquivos.id", ondelete="SET NULL"), nullable=True)
    # AUD6-S11-001/002: Admin and beat events have no production or proposal.
    beat_id = Column(Integer, ForeignKey("beats.id", ondelete="CASCADE"), nullable=True, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id", ondelete="CASCADE"), nullable=True, index=True)
    portfolio_envio_id = Column(Integer, ForeignKey("portfolio_envios.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    vista_em = Column(DateTime(timezone=True), nullable=True)


# Empty-database bootstrap uses metadata instead of running historical migrations.
event.listen(PortalNotificacaoModel.__table__, "after_create", DDL(
    "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(PortalNotificacaoModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
