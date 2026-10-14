from sqlalchemy import JSON, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from database import Base


class PortalConfiguracaoModel(Base):
    """Append-only, versioned settings for the client and producer portals (Roadmap 5.01)."""

    __tablename__ = "portal_configuracoes"
    __table_args__ = (
        CheckConstraint("portal IN ('cliente', 'produtor')", name="ck_portal_configuracoes_portal"),
        CheckConstraint("versao > 0", name="ck_portal_configuracoes_versao_positiva"),
        UniqueConstraint("portal", "versao", name="uq_portal_configuracoes_portal_versao"),
    )

    id = Column(Integer, primary_key=True)
    portal = Column(String(20), nullable=False, index=True)
    versao = Column(Integer, nullable=False)
    dados = Column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    autor_usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    restaurada_de_versao = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
