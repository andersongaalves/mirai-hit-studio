from sqlalchemy import JSON, Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AuditLogModel(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(
        Integer,
        ForeignKey("usuarios.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False, index=True)
    entity_id = Column(String(64), nullable=True)
    metadata_json = Column(JSON, default=dict, nullable=False)
    request_id = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    actor = relationship("UsuarioModel")
