"""Create catalog stages with percentage weights (Roadmap 3.0, 5.04).

Revision ID: d3f5a7b9c124
Revises: c9d2e4f6a813
"""

import sqlalchemy as sa
from alembic import op

revision = "d3f5a7b9c124"
down_revision = "c9d2e4f6a813"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: services keep working without stages; no row is changed.
    op.create_table(
        "servico_etapas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("descricao", sa.String(length=300), nullable=False),
        sa.Column("peso_percentual", sa.Numeric(5, 2), nullable=False),
        sa.Column("prazo_dias", sa.Integer(), nullable=True),
        sa.Column("unidade", sa.String(length=30), nullable=False),
        sa.Column("revisoes_incluidas", sa.Integer(), nullable=True),
        sa.Column("depende_da_anterior", sa.Boolean(), nullable=False),
        sa.Column("administrativa", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("servico_id", "ordem", name="uq_servico_etapas_servico_ordem"),
        sa.CheckConstraint("ordem > 0", name="ck_servico_etapas_ordem_positiva"),
        sa.CheckConstraint("peso_percentual >= 0 AND peso_percentual <= 100", name="ck_servico_etapas_peso"),
        sa.CheckConstraint(
            "prazo_dias IS NULL OR (prazo_dias >= 0 AND prazo_dias <= 365)", name="ck_servico_etapas_prazo"
        ),
        sa.CheckConstraint(
            "revisoes_incluidas IS NULL OR (revisoes_incluidas >= 0 AND revisoes_incluidas <= 20)",
            name="ck_servico_etapas_revisoes",
        ),
        sa.CheckConstraint(
            "ordem > 1 OR depende_da_anterior = false", name="ck_servico_etapas_primeira_sem_dependencia"
        ),
    )
    op.create_index("ix_servico_etapas_servico_id", "servico_etapas", ["servico_id"])


def downgrade():
    op.drop_index("ix_servico_etapas_servico_id", table_name="servico_etapas")
    op.drop_table("servico_etapas")
