"""Freeze catalog origin and stage values in proposals (Roadmap 3.0, 5.05).

Revision ID: e5a7c9d1f246
Revises: d3f5a7b9c124
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e5a7c9d1f246"
down_revision = "d3f5a7b9c124"
branch_labels = None
depends_on = None


def upgrade():
    # Additive and nullable: existing proposals keep no snapshot; nothing is backfilled,
    # because a later catalog must never rewrite an earlier contract.
    op.add_column(
        "propostas",
        sa.Column(
            "snapshot_economico",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=True,
        ),
    )
    op.add_column(
        "propostas",
        sa.Column("snapshot_congelado_em", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade():
    op.drop_column("propostas", "snapshot_congelado_em")
    op.drop_column("propostas", "snapshot_economico")
