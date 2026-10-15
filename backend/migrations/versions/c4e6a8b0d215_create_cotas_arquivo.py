"""File quotas per service and per production (Roadmap 3.0, 5.09).

Revision ID: c4e6a8b0d215
Revises: b2d4f6a8c913
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "c4e6a8b0d215"
down_revision = "b2d4f6a8c913"
branch_labels = None
depends_on = None

TIPO_CHECK = "tipo IN ('material', 'referencia', 'previa', 'entrega')"
LIMITES_CHECK = (
    "(max_arquivos IS NULL OR max_arquivos BETWEEN 1 AND 100)"
    " AND (max_versoes IS NULL OR max_versoes BETWEEN 1 AND 50)"
    " AND (max_tamanho_mb IS NULL OR max_tamanho_mb BETWEEN 1 AND 50)"
    " AND (max_total_mb IS NULL OR max_total_mb BETWEEN 1 AND 5000)"
)


def _limits():
    return [
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("max_arquivos", sa.Integer(), nullable=True),
        sa.Column("max_versoes", sa.Integer(), nullable=True),
        sa.Column("max_tamanho_mb", sa.Integer(), nullable=True),
        sa.Column("max_total_mb", sa.Integer(), nullable=True),
        sa.Column("formatos", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
    ]


def upgrade():
    # Additive only: without quota rows, uploads keep the current global limits.
    op.create_table(
        "servico_cotas_arquivo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="CASCADE"), nullable=False),
        *_limits(),
        sa.UniqueConstraint("servico_id", "tipo", name="uq_servico_cotas_arquivo_servico_tipo"),
        sa.CheckConstraint(TIPO_CHECK, name="ck_servico_cotas_arquivo_tipo"),
        sa.CheckConstraint(LIMITES_CHECK, name="ck_servico_cotas_arquivo_limites"),
    )
    op.create_index("ix_servico_cotas_arquivo_servico_id", "servico_cotas_arquivo", ["servico_id"])
    op.create_table(
        "producao_cotas_arquivo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        *_limits(),
        sa.Column("origem", sa.String(length=20), nullable=False, server_default="contrato"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("producao_id", "tipo", name="uq_producao_cotas_arquivo_producao_tipo"),
        sa.CheckConstraint(TIPO_CHECK, name="ck_producao_cotas_arquivo_tipo"),
        sa.CheckConstraint(LIMITES_CHECK, name="ck_producao_cotas_arquivo_limites"),
        sa.CheckConstraint("origem IN ('contrato', 'admin')", name="ck_producao_cotas_arquivo_origem"),
    )
    op.create_index("ix_producao_cotas_arquivo_producao_id", "producao_cotas_arquivo", ["producao_id"])


def downgrade():
    op.drop_index("ix_producao_cotas_arquivo_producao_id", table_name="producao_cotas_arquivo")
    op.drop_table("producao_cotas_arquivo")
    op.drop_index("ix_servico_cotas_arquivo_servico_id", table_name="servico_cotas_arquivo")
    op.drop_table("servico_cotas_arquivo")
