"""Persist optional public request idempotency keys (I.2).

Revision ID: b8c41e7d290a
Revises: f2a8c4e6d901
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c41e7d290a"
down_revision = "f2a8c4e6d901"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orcamentos", sa.Column("idempotency_key", sa.String(36), nullable=True))
    op.add_column("orcamentos", sa.Column("request_hash", sa.String(64), nullable=True))
    op.create_index("ix_orcamentos_idempotency_key", "orcamentos", ["idempotency_key"], unique=True)


def downgrade():
    op.drop_index("ix_orcamentos_idempotency_key", table_name="orcamentos")
    op.drop_column("orcamentos", "request_hash")
    op.drop_column("orcamentos", "idempotency_key")
