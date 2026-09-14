"""Add active state to administrative users.

Revision ID: c8f4e2d91a7b
Revises: a4c82d91f6e3
"""

from alembic import op
import sqlalchemy as sa


revision: str = "c8f4e2d91a7b"
down_revision: str = "a4c82d91f6e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(
            sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        )


def downgrade() -> None:
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("ativo")
