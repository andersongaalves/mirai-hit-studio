"""Beats get moods (comma-separated, like genres) for the catalog filters.

Revision ID: b2d4f6a8c0e1
Revises: f8b0d2e4a6c7
"""
import sqlalchemy as sa
from alembic import op

revision = "b2d4f6a8c0e1"
down_revision = "f8b0d2e4a6c7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("beats", sa.Column("moods", sa.String(240), server_default="", nullable=False))


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("beats") as batch:
            batch.drop_column("moods")
    else:
        op.drop_column("beats", "moods")
