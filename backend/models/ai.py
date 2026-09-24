"""Durable conversation state; no provider or delivery dependency."""

from uuid import uuid4

from sqlalchemy import (
    CheckConstraint, Column, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, DDL, event,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


def new_id():
    return str(uuid4())


class AIConversationModel(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        CheckConstraint("status IN ('open','waiting_human','closed')", name="ck_ai_conversation_status"),
        CheckConstraint("mode IN ('autonomous','copilot','human')", name="ck_ai_conversation_mode"),
        CheckConstraint("channel IN ('site','email')", name="ck_ai_conversation_channel"),
        Index("ix_ai_conversation_status", "status", "updated_at"),
        UniqueConstraint("channel", "external_thread_id", name="uq_ai_conversation_thread"),
    )
    id = Column(String(36), primary_key=True, default=new_id)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True, index=True)
    anonymous_session_id = Column(String(36), nullable=True, unique=True)
    assigned_user_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    channel = Column(String(10), nullable=False)
    external_thread_id = Column(String(200), nullable=True)
    sender_reference = Column(String(200), nullable=True)
    status = Column(String(20), nullable=False, default="open", server_default="open")
    mode = Column(String(20), nullable=False, default="human", server_default="human")
    handoff_reason = Column(String(30), nullable=True)
    version = Column(Integer, nullable=False, default=0, server_default="0")
    claim_token = Column(String(36), nullable=True)
    lease_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    cliente = relationship("ClienteModel")
    assigned_user = relationship("UsuarioModel")
    messages = relationship("AIMessageModel", back_populates="conversation")


class AIMessageModel(Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        UniqueConstraint("conversation_id", "channel", "external_message_id", name="uq_ai_message_inbound"),
        UniqueConstraint("reply_to_id", name="uq_ai_message_reply"),
        CheckConstraint("direction IN ('inbound','outbound')", name="ck_ai_message_direction"),
        CheckConstraint("role IN ('user','assistant')", name="ck_ai_message_role"),
        CheckConstraint("channel IN ('site','email')", name="ck_ai_message_channel"),
        CheckConstraint("processing_status IN ('pending','processing','completed','failed')", name="ck_ai_message_processing"),
        CheckConstraint("kind IN ('message','reply','suggestion')", name="ck_ai_message_kind"),
        Index("ix_ai_message_history", "conversation_id", "created_at", "id"),
        Index("ix_ai_message_pending", "conversation_id", "processing_status"),
    )
    id = Column(String(36), primary_key=True, default=new_id)
    conversation_id = Column(String(36), ForeignKey("ai_conversations.id"), nullable=False)
    direction = Column(String(10), nullable=False)
    role = Column(String(10), nullable=False)
    channel = Column(String(10), nullable=False)
    external_message_id = Column(String(200), nullable=True)
    reply_to_id = Column(String(36), ForeignKey("ai_messages.id"), nullable=True)
    kind = Column(String(12), nullable=False, default="message", server_default="message")
    content = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processing_status = Column(String(12), nullable=False, default="pending", server_default="pending")
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    result_action = Column(String(12), nullable=True)
    reason = Column(String(30), nullable=True)
    error_code = Column(String(40), nullable=True)
    request_id = Column(String(64), nullable=True)
    conversation = relationship("AIConversationModel", back_populates="messages")


class AIEmailThreadModel(Base):
    """Email-only correlation data kept outside the channel-neutral core."""

    __tablename__ = "ai_email_threads"
    __table_args__ = (
        UniqueConstraint("root_message_id", name="uq_ai_email_thread_root_message"),
        Index("ix_ai_email_thread_sender", "sender_email"),
    )
    conversation_id = Column(
        String(36), ForeignKey("ai_conversations.id"), primary_key=True
    )
    sender_email = Column(String(254), nullable=False)
    subject = Column(String(200), nullable=False)
    root_message_id = Column(String(998), nullable=False)
    last_inbound_message_id = Column(String(998), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    conversation = relationship("AIConversationModel")


# Bootstrap uses metadata directly; keep private-table protection equivalent to Alembic.
for table in (AIConversationModel.__table__, AIMessageModel.__table__, AIEmailThreadModel.__table__):
    event.listen(table, "after_create", DDL(
        "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
    ).execute_if(dialect="postgresql"))
    for role in ("anon", "authenticated"):
        event.listen(table, "after_create", DDL(
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
            "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
        ).execute_if(dialect="postgresql"))
