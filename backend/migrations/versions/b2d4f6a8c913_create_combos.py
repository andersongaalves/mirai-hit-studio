"""Create catalog combos of services (Roadmap 3.0, 5.08).

Revision ID: b2d4f6a8c913
Revises: a9c1e3f5b702
"""

import sqlalchemy as sa
from alembic import op

revision = "b2d4f6a8c913"
down_revision = "a9c1e3f5b702"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: two new catalog tables; proposals reference combos only inside JSON.
    op.create_table(
        "combos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("descricao", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("preco_base", sa.Numeric(12, 2), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("preco_base >= 0", name="ck_combos_preco_base"),
    )
    op.create_table(
        "combo_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("combo_id", sa.Integer(), sa.ForeignKey("combos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.UniqueConstraint("combo_id", "servico_id", name="uq_combo_itens_combo_servico"),
        sa.UniqueConstraint("combo_id", "ordem", name="uq_combo_itens_combo_ordem"),
        sa.CheckConstraint("ordem > 0", name="ck_combo_itens_ordem"),
    )
    op.create_index("ix_combo_itens_combo_id", "combo_itens", ["combo_id"])


def downgrade():
    op.drop_index("ix_combo_itens_combo_id", table_name="combo_itens")
    op.drop_table("combo_itens")
    op.drop_table("combos")
