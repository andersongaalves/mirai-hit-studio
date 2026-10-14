"""Create versioned portal settings (Roadmap 3.0, 5.01).

Revision ID: b4e6f8a1c302
Revises: d8a7b1c9e240
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b4e6f8a1c302"
down_revision = "d8a7b1c9e240"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: portals keep their built-in defaults until an admin publishes a version.
    op.create_table(
        "portal_configuracoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("portal", sa.String(length=20), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("dados", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False),
        sa.Column(
            "autor_usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("restaurada_de_versao", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("portal IN ('cliente', 'produtor')", name="ck_portal_configuracoes_portal"),
        sa.CheckConstraint("versao > 0", name="ck_portal_configuracoes_versao_positiva"),
        sa.UniqueConstraint("portal", "versao", name="uq_portal_configuracoes_portal_versao"),
    )
    op.create_index("ix_portal_configuracoes_portal", "portal_configuracoes", ["portal"])


def downgrade():
    op.drop_index("ix_portal_configuracoes_portal", table_name="portal_configuracoes")
    op.drop_table("portal_configuracoes")
