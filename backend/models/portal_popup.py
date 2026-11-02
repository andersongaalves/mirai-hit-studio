from database import Base
from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
)
from sqlalchemy.sql import func


class PortalPopupModel(Base):
    """A pop-up the Admin sends to the client and/or producer portals."""

    __tablename__ = "portal_popups"
    __table_args__ = (
        CheckConstraint("publico IN ('cliente', 'produtor', 'todos')", name="ck_portal_popups_publico"),
        CheckConstraint("tema IN ('ciano', 'roxo', 'amarelo', 'verde', 'vermelho')", name="ck_portal_popups_tema"),
        CheckConstraint("tamanho IN ('pequeno', 'medio')", name="ck_portal_popups_tamanho"),
        CheckConstraint("frequencia IN ('uma_vez', 'cada_sessao')", name="ck_portal_popups_frequencia"),
        CheckConstraint("fim IS NULL OR inicio IS NULL OR fim > inicio", name="ck_portal_popups_periodo"),
    )

    id = Column(Integer, primary_key=True)
    titulo = Column(String(80), nullable=False)
    mensagem = Column(Text, nullable=False)
    publico = Column(String(10), nullable=False)
    tema = Column(String(12), nullable=False, default="ciano", server_default="ciano")
    tamanho = Column(String(10), nullable=False, default="pequeno", server_default="pequeno")
    botao_rotulo = Column(String(40), nullable=True)
    botao_url = Column(String(300), nullable=True)
    frequencia = Column(String(12), nullable=False, default="uma_vez", server_default="uma_vez")
    inicio = Column(DateTime(timezone=True), nullable=True)
    fim = Column(DateTime(timezone=True), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, server_default="true")
    autor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PortalPopupVistoModel(Base):
    """Who closed a pop-up ("show once" pop-ups do not come back to them)."""

    __tablename__ = "portal_popup_vistos"
    __table_args__ = (UniqueConstraint("popup_id", "usuario_id", name="uq_portal_popup_vistos_popup_usuario"),)

    id = Column(Integer, primary_key=True)
    popup_id = Column(Integer, ForeignKey("portal_popups.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    visto_em = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# Empty-database bootstrap uses metadata instead of running historical migrations.
for _table in (PortalPopupModel.__table__, PortalPopupVistoModel.__table__):
    event.listen(_table, "after_create", DDL(
        "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
    ).execute_if(dialect="postgresql"))
    for _role in ("anon", "authenticated"):
        event.listen(_table, "after_create", DDL(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + _role + "') "
            "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + _role + "; END IF; END; $$"
        ).execute_if(dialect="postgresql"))
