"""One progressive commercial briefing per AI conversation."""

from sqlalchemy import CheckConstraint, Column, DateTime, DDL, event, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base


class AIBriefingModel(Base):
    __tablename__ = "ai_briefings"
    __table_args__ = (
        CheckConstraint("status IN ('draft','submitted')", name="ck_ai_briefing_status"),
    )

    conversation_id = Column(String(36), ForeignKey("ai_conversations.id"), primary_key=True)
    service_id = Column(Integer, ForeignKey("servicos.id"), nullable=True)
    interest = Column(String(100), nullable=True)
    contact_name = Column(String(120), nullable=True)
    contact_email = Column(String(150), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    data_json = Column(JSON, nullable=False, default=dict)
    status = Column(String(12), nullable=False, default="draft", server_default="draft")
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=True, unique=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    submitted_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("AIConversationModel")
    service = relationship("ServicoModel")
    orcamento = relationship("OrcamentoModel")


event.listen(AIBriefingModel.__table__, "after_create", DDL(
    "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(AIBriefingModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
