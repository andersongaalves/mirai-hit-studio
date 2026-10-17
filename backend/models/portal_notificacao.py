from database import Base
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)


class PortalNotificacaoModel(Base):
    __tablename__ = "portal_notificacoes"
    __table_args__ = (
        UniqueConstraint("usuario_id", "chave_evento", name="uq_portal_notificacao_usuario_evento"),
        CheckConstraint("papel IN ('cliente', 'produtor')", name="ck_portal_notificacao_papel"),
        CheckConstraint("producao_id IS NOT NULL OR proposta_id IS NOT NULL", name="ck_portal_notificacao_contexto"),
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
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    vista_em = Column(DateTime(timezone=True), nullable=True)
