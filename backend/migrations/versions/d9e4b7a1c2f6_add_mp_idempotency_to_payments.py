"""Add provider idempotency key to payments.

Revision ID: d9e4b7a1c2f6
Revises: c4f8a2d19e73
"""

from alembic import op
import sqlalchemy as sa


revision: str = "d9e4b7a1c2f6"
down_revision: str = "c4f8a2d19e73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("pagamentos") as batch_op:
        batch_op.add_column(
            sa.Column("provider_idempotency_key", sa.String(length=128), nullable=True)
        )
        batch_op.create_unique_constraint(
            "uq_pagamentos_provider_idempotency_key",
            ["provider_idempotency_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("pagamentos") as batch_op:
        batch_op.drop_constraint(
            "uq_pagamentos_provider_idempotency_key",
            type_="unique",
        )
        batch_op.drop_column("provider_idempotency_key")
