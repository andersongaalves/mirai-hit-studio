"""Create propostas.

Revision ID: e7a42c6b913f
Revises: d1bdcc7920ab
"""

from alembic import op
import sqlalchemy as sa

revision: str = "e7a42c6b913f"
down_revision: str = "d1bdcc7920ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Python-side defaults stay in the model; only server defaults belong here.
    op.create_table(
        "propostas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("orcamento_id", sa.Integer(), nullable=False),
        sa.Column("numero", sa.String(length=30), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("produtor_id", sa.Integer(), nullable=True),
        sa.Column("cliente_snapshot", sa.JSON(), nullable=False),
        sa.Column("objeto", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=False),
        sa.Column("itens_json", sa.JSON(), nullable=False),
        sa.Column("pagamentos_json", sa.JSON(), nullable=False),
        sa.Column("condicoes", sa.Text(), nullable=False),
        sa.Column("totais_json", sa.JSON(), nullable=False),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("gerada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aprovada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["orcamento_id"], ["orcamentos.id"]),
        sa.ForeignKeyConstraint(["produtor_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_propostas_id"), "propostas", ["id"], unique=False)
    op.create_index(op.f("ix_propostas_orcamento_id"), "propostas", ["orcamento_id"], unique=True)
    op.create_index(op.f("ix_propostas_numero"), "propostas", ["numero"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_propostas_numero"), table_name="propostas")
    op.drop_index(op.f("ix_propostas_orcamento_id"), table_name="propostas")
    op.drop_index(op.f("ix_propostas_id"), table_name="propostas")
    op.drop_table("propostas")
