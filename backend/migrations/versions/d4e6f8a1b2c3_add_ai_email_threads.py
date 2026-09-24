"""Persist email-only threading and delivery correlation data."""

from alembic import op
import sqlalchemy as sa


revision = "d4e6f8a1b2c3"
down_revision = "c8a1d6e4b209"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_email_threads",
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id"), primary_key=True),
        sa.Column("sender_email", sa.String(254), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("root_message_id", sa.String(998), nullable=False),
        sa.Column("last_inbound_message_id", sa.String(998), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("root_message_id", name="uq_ai_email_thread_root_message"),
    )
    op.create_index("ix_ai_email_thread_sender", "ai_email_threads", ["sender_email"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE ai_email_threads ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            op.execute(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
                "THEN REVOKE ALL ON TABLE ai_email_threads FROM " + role + "; END IF; END; $$"
            )


def downgrade():
    op.drop_index("ix_ai_email_thread_sender", table_name="ai_email_threads")
    op.drop_table("ai_email_threads")
