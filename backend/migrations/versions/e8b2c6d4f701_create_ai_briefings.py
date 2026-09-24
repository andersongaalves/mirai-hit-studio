"""Persist progressive AI briefings and their commercial conversion."""

from alembic import op
import sqlalchemy as sa


revision = "e8b2c6d4f701"
down_revision = "d4e6f8a1b2c3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_briefings",
        sa.Column("conversation_id", sa.String(36), sa.ForeignKey("ai_conversations.id"), primary_key=True),
        sa.Column("service_id", sa.Integer(), sa.ForeignKey("servicos.id"), nullable=True),
        sa.Column("interest", sa.String(100), nullable=True),
        sa.Column("contact_name", sa.String(120), nullable=True),
        sa.Column("contact_email", sa.String(150), nullable=True),
        sa.Column("contact_phone", sa.String(30), nullable=True),
        sa.Column("data_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="draft"),
        sa.Column("orcamento_id", sa.Integer(), sa.ForeignKey("orcamentos.id"), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('draft','submitted')", name="ck_ai_briefing_status"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE ai_briefings ENABLE ROW LEVEL SECURITY")
        for role in ("anon", "authenticated"):
            op.execute(
                "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '" + role + "') "
                "THEN REVOKE ALL ON TABLE ai_briefings FROM " + role + "; END IF; END; $$"
            )


def downgrade():
    op.drop_table("ai_briefings")
