"""Display name for accounts, independent of the login username (no backfill).

Revision ID: b4d6f8a0c357
Revises: a2c4e6f8b135
"""
import sqlalchemy as sa
from alembic import op

revision = "b4d6f8a0c357"
down_revision = "a2c4e6f8b135"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(sa.Column("nome_exibicao", sa.String(80), nullable=True))


def downgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("nome_exibicao")
