"""Previous sent version of a reopened proposal, for comparison (AUD6-S05-002).

Revision ID: f2b4d6e8a0c3
Revises: e1a3c5d7f9b2
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f2b4d6e8a0c3"
down_revision = "e1a3c5d7f9b2"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN: no table rebuild on SQLite, nothing backfilled.
    op.add_column("propostas", sa.Column(
        "envio_anterior", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))


def downgrade():
    op.execute("ALTER TABLE propostas DROP COLUMN envio_anterior")
