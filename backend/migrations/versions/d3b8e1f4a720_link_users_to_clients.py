"""link users to clients

Revision ID: d3b8e1f4a720
Revises: c1e7a4b9d302
Create Date: 2026-10-02
"""

import sqlalchemy as sa

from alembic import op

revision = "d3b8e1f4a720"
down_revision = "c1e7a4b9d302"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(sa.Column("cliente_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_usuarios_cliente_id_clientes",
            "clientes",
            ["cliente_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_unique_constraint("uq_usuarios_cliente_id", ["cliente_id"])
        batch_op.create_check_constraint(
            "ck_usuarios_role_cliente_vinculo",
            "(role = 'cliente' AND cliente_id IS NOT NULL) OR "
            "(role IN ('admin', 'produtor') AND cliente_id IS NULL)",
        )


def downgrade():
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_constraint("ck_usuarios_role_cliente_vinculo", type_="check")
        batch_op.drop_constraint("uq_usuarios_cliente_id", type_="unique")
        batch_op.drop_constraint("fk_usuarios_cliente_id_clientes", type_="foreignkey")
        batch_op.drop_column("cliente_id")
