"""Classify historical test chains without deleting financial or audit evidence.

Revision ID: d8a7b1c9e240
Revises: c5f2a7d9e184
"""
import sqlalchemy as sa
from alembic import op

revision = "d8a7b1c9e240"
down_revision = "c5f2a7d9e184"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("clientes", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("orcamentos", sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_clientes_is_test", "clientes", ["is_test"])
    op.create_index("ix_orcamentos_is_test", "orcamentos", ["is_test"])

    connection = op.get_bind()
    # Only explicitly inventoried, declared test chains. Exclude the protected
    # Yonda identity and descendants even if a historical identifier is reused.
    connection.execute(sa.text("""
        UPDATE clientes AS c SET is_test = TRUE
        WHERE c.id IN (90, 91, 92, 93)
          AND NOT EXISTS (
              SELECT 1 FROM usuarios u
              WHERE u.cliente_id = c.id AND (u.role IN ('admin', 'produtor') OR u.id = 48)
          )
          AND NOT EXISTS (
              SELECT 1 FROM orcamentos o WHERE o.cliente_id = c.id AND o.id = 238
          )
    """))
    connection.execute(sa.text("""
        UPDATE orcamentos AS o SET is_test = TRUE
        WHERE o.id IN (234, 237, 239, 240)
          AND o.id <> 238
          AND (o.cliente_id IS NULL OR EXISTS (
              SELECT 1 FROM clientes c WHERE c.id = o.cliente_id AND c.is_test = TRUE
          ))
          AND NOT EXISTS (
              SELECT 1 FROM propostas p WHERE p.orcamento_id = o.id AND p.id = 73
          )
    """))


def downgrade():
    op.drop_index("ix_orcamentos_is_test", table_name="orcamentos")
    op.drop_index("ix_clientes_is_test", table_name="clientes")
    op.drop_column("orcamentos", "is_test")
    op.drop_column("clientes", "is_test")
