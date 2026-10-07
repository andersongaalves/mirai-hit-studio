"""Add per-user authentication version.

Revision ID: b3e6f9a2c741
Revises: a41b7d8de6d7
"""

import sqlalchemy as sa
from alembic import op

revision = "b3e6f9a2c741"
down_revision = "a41b7d8de6d7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "usuarios",
        sa.Column("auth_version", sa.Integer(), server_default=sa.text("0"), nullable=True),
    )
    op.execute("UPDATE usuarios SET auth_version = 0 WHERE auth_version IS NULL")
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.alter_column("auth_version", nullable=False)
        batch_op.create_check_constraint(
            "ck_usuarios_auth_version_nao_negativa",
            "auth_version >= 0",
        )


def downgrade():
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_constraint(
            "ck_usuarios_auth_version_nao_negativa",
            type_="check",
        )
        batch_op.drop_column("auth_version")
