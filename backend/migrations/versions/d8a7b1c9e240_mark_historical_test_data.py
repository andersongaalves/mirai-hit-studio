"""Classify historical test chains without deleting financial or audit evidence.

Revision ID: d8a7b1c9e240
Revises: a7d3e5f9c210
"""

import sqlalchemy as sa
from alembic import op

revision = "d8a7b1c9e240"
down_revision = "a7d3e5f9c210"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "clientes",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "orcamentos",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "usuarios",
        sa.Column("is_test", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_clientes_is_test", "clientes", ["is_test"])
    op.create_index("ix_orcamentos_is_test", "orcamentos", ["is_test"])

    connection = op.get_bind()
    # Match the inventoried budget/proposal/customer links, never a customer-wide
    # commercial inference. A newly added real proposal remains real.
    connection.execute(
        sa.text("""
        UPDATE orcamentos AS o SET is_test = TRUE
        WHERE EXISTS (SELECT 1 FROM propostas p WHERE p.orcamento_id = o.id AND (
            (o.id = 234 AND p.id = 67 AND o.cliente_id = 90) OR
            (o.id = 237 AND p.id = 70 AND o.cliente_id = 93) OR
            (o.id = 239 AND p.id = 71 AND o.cliente_id = 93) OR
            (o.id = 240 AND p.id = 72 AND o.cliente_id = 93)))
          AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.cliente_id=o.cliente_id
            AND (u.id=48 OR lower(trim(u.username))='yonda' OR u.role IN ('admin','produtor')))
          AND o.cliente_id <> 94
          AND NOT EXISTS (
              SELECT 1 FROM propostas p LEFT JOIN cobrancas c ON c.proposta_id=p.id
              LEFT JOIN pagamentos pay ON pay.cobranca_id=c.id
              WHERE p.orcamento_id=o.id AND (p.id=73 OR c.id=74 OR c.cliente_id=94 OR pay.id=85)
          )
          AND NOT EXISTS (SELECT 1 FROM producoes pr WHERE pr.orcamento_id=o.id AND pr.id=48)
    """)
    )
    connection.execute(
        sa.text("""
        UPDATE clientes AS c SET is_test = TRUE
        WHERE c.id IN (90,91,92,93)
          AND NOT EXISTS (SELECT 1 FROM usuarios u WHERE u.cliente_id=c.id
            AND (u.id=48 OR lower(trim(u.username))='yonda' OR u.role IN ('admin','produtor')))
          AND NOT EXISTS (SELECT 1 FROM orcamentos o WHERE o.cliente_id=c.id AND o.is_test=FALSE)
          AND (EXISTS (SELECT 1 FROM orcamentos o WHERE o.cliente_id=c.id AND o.is_test=TRUE)
            OR EXISTS (SELECT 1 FROM usuarios u WHERE u.cliente_id=c.id AND u.role='cliente'
              AND ((c.id=91 AND u.id=45) OR (c.id=92 AND u.id=47))))
    """)
    )
    connection.execute(
        sa.text("""
        UPDATE usuarios SET is_test=TRUE WHERE role='cliente' AND id IN (45,46,47)
          AND EXISTS (SELECT 1 FROM clientes c WHERE c.id=usuarios.cliente_id AND c.is_test=TRUE
            AND ((usuarios.id=45 AND c.id=91) OR (usuarios.id=46 AND c.id=93) OR (usuarios.id=47 AND c.id=92)))
          AND lower(trim(username)) <> 'yonda'
    """)
    )


def downgrade():
    op.drop_column("usuarios", "is_test")
    op.drop_index("ix_orcamentos_is_test", table_name="orcamentos")
    op.drop_index("ix_clientes_is_test", table_name="clientes")
    op.drop_column("orcamentos", "is_test")
    op.drop_column("clientes", "is_test")
