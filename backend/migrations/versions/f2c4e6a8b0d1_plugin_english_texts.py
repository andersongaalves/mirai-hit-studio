"""Mirai Hit Labs: English texts for each plugin (the store is in English by default).

Revision ID: f2c4e6a8b0d1
Revises: e7b9d1f3a5c6
"""
import sqlalchemy as sa
from alembic import op

revision = "f2c4e6a8b0d1"
down_revision = "e7b9d1f3a5c6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("plugins", sa.Column("tagline_en", sa.String(160), nullable=True))
    op.add_column("plugins", sa.Column("descricao_en", sa.Text(), nullable=True))
    op.add_column("plugins", sa.Column("categoria_en", sa.String(40), nullable=True))
    op.add_column("plugins", sa.Column("recursos_en_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.add_column("plugins", sa.Column("requisitos_en", sa.Text(), nullable=True))


def downgrade():
    for column in ("requisitos_en", "recursos_en_json", "categoria_en", "descricao_en", "tagline_en"):
        op.drop_column("plugins", column)
