"""Create channel-independent conversations and messages.

Revision ID: c8a1d6e4b209
Revises: f6c2a8d4e1b9
"""

from alembic import op
import sqlalchemy as sa


revision = "c8a1d6e4b209"
down_revision = "f6c2a8d4e1b9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id"), nullable=True),
        sa.Column("anonymous_session_id", sa.String(36), nullable=True, unique=True),
        sa.Column("assigned_user_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("external_thread_id", sa.String(200), nullable=True),
        sa.Column("sender_reference", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("mode", sa.String(20), nullable=False, server_default="human"),
        sa.Column("handoff_reason", sa.String(30), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("claim_token", sa.String(36), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('open','waiting_human','closed')", name="ck_ai_conversation_status"),
        sa.CheckConstraint("mode IN ('autonomous','copilot','human')", name="ck_ai_conversation_mode"),
        sa.CheckConstraint("channel IN ('site','email')", name="ck_ai_conversation_channel"),
        sa.UniqueConstraint("channel", "external_thread_id", name="uq_ai_conversation_thread"),
    )
    op.create_index("ix_ai_conversations_cliente_id", "ai_conversations", ["cliente_id"])
    op.create_index("ix_ai_conversation_status", "ai_conversations", ["status", "updated_at"])
    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("external_message_id", sa.String(200), nullable=True),
        sa.Column("reply_to_id", sa.String(36), sa.ForeignKey("ai_messages.id"), nullable=True),
        sa.Column("kind", sa.String(12), nullable=False, server_default="message"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processing_status", sa.String(12), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("result_action", sa.String(12), nullable=True),
        sa.Column("reason", sa.String(30), nullable=True),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.UniqueConstraint("conversation_id", "channel", "external_message_id", name="uq_ai_message_inbound"),
        sa.UniqueConstraint("reply_to_id", name="uq_ai_message_reply"),
        sa.CheckConstraint("direction IN ('inbound','outbound')", name="ck_ai_message_direction"),
        sa.CheckConstraint("role IN ('user','assistant')", name="ck_ai_message_role"),
        sa.CheckConstraint("channel IN ('site','email')", name="ck_ai_message_channel"),
        sa.CheckConstraint("processing_status IN ('pending','processing','completed','failed')", name="ck_ai_message_processing"),
        sa.CheckConstraint("kind IN ('message','reply','suggestion')", name="ck_ai_message_kind"),
    )
    op.create_index("ix_ai_message_history", "ai_messages", ["conversation_id", "created_at", "id"])
    op.create_index("ix_ai_message_pending", "ai_messages", ["conversation_id", "processing_status"])
    if op.get_bind().dialect.name == "postgresql":
        for table in ("ai_conversations", "ai_messages"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            for role in ("anon", "authenticated"):
                op.execute(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                    f"THEN REVOKE ALL ON TABLE {table} FROM {role}; END IF; END; $$"
                )


def downgrade():
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
