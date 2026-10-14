"""Add an optional, immutable note to each production file version (Roadmap 3.0, 5.02).

Revision ID: a7d3e5f9c210
Revises: c5f2a7d9e184
"""

import sqlalchemy as sa
from alembic import op

revision = "a7d3e5f9c210"
down_revision = "c5f2a7d9e184"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable and without default: existing versions keep no note and nothing is rewritten.
    op.add_column(
        "producao_arquivos",
        sa.Column("observacao", sa.String(length=1000), nullable=True),
    )


def downgrade():
    op.drop_column("producao_arquivos", "observacao")
