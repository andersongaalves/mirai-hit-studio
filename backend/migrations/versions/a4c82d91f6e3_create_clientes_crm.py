"""Create clientes CRM and link budgets.

Revision ID: a4c82d91f6e3
Revises: e7a42c6b913f
"""

from alembic import op
import sqlalchemy as sa


revision: str = "a4c82d91f6e3"
down_revision: str = "e7a42c6b913f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clientes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("telefone", sa.String(length=30), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=False),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clientes_id"), "clientes", ["id"], unique=False)
    op.create_index(op.f("ix_clientes_nome"), "clientes", ["nome"], unique=False)
    op.create_index(op.f("ix_clientes_email"), "clientes", ["email"], unique=False)
    op.create_index(op.f("ix_clientes_telefone"), "clientes", ["telefone"], unique=False)
    with op.batch_alter_table("orcamentos") as batch_op:
        batch_op.add_column(sa.Column("cliente_id", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_orcamentos_cliente_id"), ["cliente_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_orcamentos_cliente_id_clientes",
            "clientes",
            ["cliente_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("orcamentos") as batch_op:
        batch_op.drop_constraint("fk_orcamentos_cliente_id_clientes", type_="foreignkey")
        batch_op.drop_index(op.f("ix_orcamentos_cliente_id"))
        batch_op.drop_column("cliente_id")
    op.drop_index(op.f("ix_clientes_telefone"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_email"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_nome"), table_name="clientes")
    op.drop_index(op.f("ix_clientes_id"), table_name="clientes")
    op.drop_table("clientes")
