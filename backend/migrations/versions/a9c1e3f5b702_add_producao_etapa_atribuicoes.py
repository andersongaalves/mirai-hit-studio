"""Stage responsibility history and executor (Roadmap 3.0, 5.07).

Revision ID: a9c1e3f5b702
Revises: f7b9d1e3a568
"""

import sqlalchemy as sa
from alembic import op

revision = "a9c1e3f5b702"
down_revision = "f7b9d1e3a568"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: one nullable column and an append-only history table.
    # Batch mode: SQLite cannot add a column with a foreign key through ALTER TABLE;
    # PostgreSQL still receives a plain ALTER TABLE ... ADD COLUMN.
    with op.batch_alter_table("producao_etapas") as batch:
        batch.add_column(
            sa.Column(
                "executor_usuario_id",
                sa.Integer(),
                sa.ForeignKey(
                    "usuarios.id",
                    ondelete="SET NULL",
                    name="fk_producao_etapas_executor_usuario_id",
                ),
                nullable=True,
            )
        )
    op.create_table(
        "producao_etapa_atribuicoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("etapa_id", sa.Integer(), sa.ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("anterior_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("novo_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column(
            "atribuido_por_usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("motivo", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_producao_etapa_atribuicoes_etapa_id", "producao_etapa_atribuicoes", ["etapa_id"])
    # Stages already created in 5.06 get their initial assignment recorded.
    op.execute(
        """
        INSERT INTO producao_etapa_atribuicoes (etapa_id, producao_id, novo_usuario_id, motivo)
        SELECT id, producao_id, responsavel_usuario_id, 'Atribuicao inicial'
        FROM producao_etapas
        """
    )


def downgrade():
    op.drop_index("ix_producao_etapa_atribuicoes_etapa_id", table_name="producao_etapa_atribuicoes")
    op.drop_table("producao_etapa_atribuicoes")
    # Batch mode rebuilds the table on SQLite, which cannot drop a column with a foreign key.
    with op.batch_alter_table("producao_etapas") as batch:
        batch.drop_constraint("fk_producao_etapas_executor_usuario_id", type_="foreignkey")
        batch.drop_column("executor_usuario_id")
