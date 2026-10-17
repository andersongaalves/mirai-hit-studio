"""Optional catalog promotions; historical proposals are unchanged.

Revision ID: f1a3c5e7b902
Revises: e8a0c2d4f659
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f1a3c5e7b902"
down_revision = "e8a0c2d4f659"
branch_labels = None
depends_on = None


def upgrade():
    for table in ("servicos", "combos"):
        op.add_column(table, sa.Column("promocao", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))


def downgrade():
    for table in ("combos", "servicos"):
        with op.batch_alter_table(table) as batch:
            batch.drop_column("promocao")
