"""Create contract stages instantiated in productions (Roadmap 3.0, 5.06).

Revision ID: f7b9d1e3a568
Revises: e5a7c9d1f246
"""

import sqlalchemy as sa
from alembic import op

revision = "f7b9d1e3a568"
down_revision = "e5a7c9d1f246"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: a new table; existing productions keep their legacy checklist.
    op.create_table(
        "producao_etapas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposta_id", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_indice", sa.Integer(), nullable=False),
        sa.Column("item_descricao", sa.String(length=200), nullable=False),
        sa.Column("servico_id", sa.Integer(), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("ordem_no_item", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("peso_percentual", sa.Numeric(5, 2), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("prazo_dias", sa.Integer(), nullable=True),
        sa.Column("unidade", sa.String(length=30), nullable=False),
        sa.Column("revisoes_incluidas", sa.Integer(), nullable=True),
        sa.Column("depende_da_anterior", sa.Boolean(), nullable=False),
        sa.Column("administrativa", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pendente"),
        sa.Column("prazo", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "responsavel_usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("iniciada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("producao_id", "ordem", name="uq_producao_etapas_producao_ordem"),
        sa.CheckConstraint("ordem > 0 AND ordem_no_item > 0 AND item_indice > 0", name="ck_producao_etapas_ordem"),
        sa.CheckConstraint(
            "status IN ('pendente', 'em_andamento', 'em_revisao', 'concluida')",
            name="ck_producao_etapas_status",
        ),
        sa.CheckConstraint("peso_percentual >= 0 AND peso_percentual <= 100", name="ck_producao_etapas_peso"),
        sa.CheckConstraint("valor >= 0", name="ck_producao_etapas_valor"),
        sa.CheckConstraint(
            "ordem_no_item > 1 OR depende_da_anterior = false",
            name="ck_producao_etapas_primeira_sem_dependencia",
        ),
        sa.CheckConstraint(
            "(status = 'concluida') = (concluida_em IS NOT NULL)",
            name="ck_producao_etapas_conclusao",
        ),
    )
    op.create_index("ix_producao_etapas_producao_id", "producao_etapas", ["producao_id"])


def downgrade():
    op.drop_index("ix_producao_etapas_producao_id", table_name="producao_etapas")
    op.drop_table("producao_etapas")
