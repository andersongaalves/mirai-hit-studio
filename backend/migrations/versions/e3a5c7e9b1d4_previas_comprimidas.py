"""Previews of delivered productions are compressed once: when it happened.

Revision ID: e3a5c7e9b1d4
Revises: d1f3a5c7e9b2
"""
import sqlalchemy as sa
from alembic import op

revision = "e3a5c7e9b1d4"
down_revision = "d1f3a5c7e9b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("producao_arquivos", sa.Column("comprimido_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producao_arquivos") as batch:
            batch.drop_column("comprimido_em")
    else:
        op.drop_column("producao_arquivos", "comprimido_em")
