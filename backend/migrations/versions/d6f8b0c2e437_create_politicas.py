"""Contractual portal policies and review counting (Roadmap 3.0, 5.10).

Revision ID: d6f8b0c2e437
Revises: c4e6a8b0d215
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6f8b0c2e437"
down_revision = "c4e6a8b0d215"
branch_labels = None
depends_on = None


def _json():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    # Additive only: without rows, every policy keeps its system default (today's behaviour).
    op.create_table(
        "politicas_globais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("dados", _json(), nullable=False),
        sa.Column("autor_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("restaurada_de_versao", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("versao > 0", name="ck_politicas_globais_versao_positiva"),
        sa.UniqueConstraint("versao", name="uq_politicas_globais_versao"),
    )
    op.create_table(
        "servico_politicas",
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("dados", _json(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "producao_politicas",
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("contrato", _json(), nullable=True),
        sa.Column("excecao", _json(), nullable=True),
        sa.Column("motivo", sa.String(length=500), nullable=True),
        sa.Column("atualizado_por_usuario_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column(
        "producao_etapas",
        sa.Column("revisoes_usadas", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    with op.batch_alter_table("producao_etapas") as batch:
        batch.drop_column("revisoes_usadas")
    op.drop_table("producao_politicas")
    op.drop_table("servico_politicas")
    op.drop_table("politicas_globais")
