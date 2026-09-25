"""Technical AI measurements, never prompts, contacts or tool arguments."""
from uuid import uuid4

from sqlalchemy import Column, DateTime, DDL, event, ForeignKey, Integer, JSON, Numeric, String, CheckConstraint, Index
from sqlalchemy.sql import func
from database import Base


class AIUsageEventModel(Base):
    __tablename__ = "ai_usage_events"
    __table_args__ = (
        CheckConstraint("kind IN ('provider','tool','turn','copilot_generated','copilot_used')", name="ck_ai_usage_kind"),
        CheckConstraint("channel IN ('site','email')", name="ck_ai_usage_channel"),
        Index("ix_ai_usage_created_channel", "created_at", "channel"),
    )
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    conversation_id = Column(String(36), ForeignKey("ai_conversations.id"), nullable=False)
    message_id = Column(String(36), ForeignKey("ai_messages.id"), nullable=True)
    channel = Column(String(10), nullable=False)
    kind = Column(String(20), nullable=False)
    name = Column(String(100), nullable=True)
    provider = Column(String(30), nullable=True)
    model = Column(String(100), nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cached_input_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cycle = Column(Integer, nullable=True)
    result = Column(String(30), nullable=False)
    error_code = Column(String(50), nullable=True)
    request_id = Column(String(71), nullable=True)
    estimated_cost = Column(Numeric(20, 10), nullable=True)
    currency = Column(String(3), nullable=True)
    rate_snapshot = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


event.listen(AIUsageEventModel.__table__, "after_create", DDL(
    "ALTER TABLE %(fullname)s ENABLE ROW LEVEL SECURITY"
).execute_if(dialect="postgresql"))
for role in ("anon", "authenticated"):
    event.listen(AIUsageEventModel.__table__, "after_create", DDL(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
        "THEN REVOKE ALL ON TABLE %(fullname)s FROM " + role + "; END IF; END; $$"
    ).execute_if(dialect="postgresql"))
