"""Add payment reconciliation and webhook events.

Revision ID: e2f7c1a9b4d8
Revises: d9e4b7a1c2f6
"""

from alembic import op
import sqlalchemy as sa


revision: str = "e2f7c1a9b4d8"
down_revision: str = "d9e4b7a1c2f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pagamentos") as batch_op:
        batch_op.alter_column(
            "provider_payment_id",
            new_column_name="provider_order_id",
            existing_type=sa.String(length=200),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("reconciliation_status", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("reconciliation_reason", sa.String(length=64), nullable=True))
        batch_op.create_check_constraint(
            "ck_pagamentos_reconciliation_status_valido",
            "reconciliation_status IS NULL OR reconciliation_status IN ('required', 'conflict')",
        )
        batch_op.create_index("ix_pagamentos_reconciliation_status", ["reconciliation_status"])

    op.create_table(
        "provider_webhook_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pagamento_id", sa.Integer(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=200), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=True),
        sa.Column("provider_event_id", sa.String(length=200), nullable=True),
        sa.Column("provider_request_id", sa.String(length=128), nullable=False),
        sa.Column("deduplication_key", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('received', 'processed', 'ignored', 'conflict', 'failed')",
            name="ck_provider_webhook_events_status_valido",
        ),
        sa.ForeignKeyConstraint(["pagamento_id"], ["pagamentos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deduplication_key",
            name="uq_provider_webhook_events_deduplication_key",
        ),
    )
    op.create_index("ix_provider_webhook_events_id", "provider_webhook_events", ["id"])
    op.create_index(
        "ix_provider_webhook_events_pagamento_id",
        "provider_webhook_events",
        ["pagamento_id"],
    )
    op.create_index(
        "ix_provider_webhook_events_resource_id",
        "provider_webhook_events",
        ["resource_id"],
    )
    op.create_index(
        "ix_provider_webhook_events_status",
        "provider_webhook_events",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_provider_webhook_events_status", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_resource_id", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_pagamento_id", table_name="provider_webhook_events")
    op.drop_index("ix_provider_webhook_events_id", table_name="provider_webhook_events")
    op.drop_table("provider_webhook_events")

    with op.batch_alter_table("pagamentos") as batch_op:
        batch_op.drop_index("ix_pagamentos_reconciliation_status")
        batch_op.drop_constraint("ck_pagamentos_reconciliation_status_valido", type_="check")
        batch_op.drop_column("reconciliation_reason")
        batch_op.drop_column("reconciliation_status")
        batch_op.alter_column(
            "provider_order_id",
            new_column_name="provider_payment_id",
            existing_type=sa.String(length=200),
            existing_nullable=True,
        )
