"""Store content-free AI measurements that cannot be derived from messages."""
from alembic import op
import sqlalchemy as sa

revision = "f2a8c4e6d901"
down_revision = "e8b2c6d4f701"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_usage_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("message_id", sa.String(36), sa.ForeignKey("ai_messages.id"), nullable=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("provider", sa.String(30), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cached_input_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cycle", sa.Integer(), nullable=True),
        sa.Column("result", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(50), nullable=True),
        sa.Column("request_id", sa.String(71), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(20, 10), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("rate_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("kind IN ('provider','tool','turn','copilot_generated','copilot_used')", name="ck_ai_usage_kind"),
        sa.CheckConstraint("channel IN ('site','email')", name="ck_ai_usage_channel"),
    )
    op.create_index("ix_ai_usage_created_channel", "ai_usage_events", ["created_at", "channel"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE ai_usage_events ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
                       "THEN REVOKE ALL ON TABLE ai_usage_events FROM " + role + "; END IF; END; $$")


def downgrade():
    op.drop_table("ai_usage_events")
