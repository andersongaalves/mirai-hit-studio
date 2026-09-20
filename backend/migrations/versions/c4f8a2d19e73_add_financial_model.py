"""Add financial receivables and payments.

Revision ID: c4f8a2d19e73
Revises: b7d3e9a1c5f2
"""

from alembic import op
import sqlalchemy as sa


revision: str = "c4f8a2d19e73"
down_revision: str = "b7d3e9a1c5f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cobrancas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("proposta_id", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), nullable=True),
        sa.Column("valor_total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("moeda", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("vencimento", sa.DateTime(timezone=True), nullable=True),
        sa.Column("referencia_externa", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("moeda = 'BRL'", name="ck_cobrancas_moeda_brl"),
        sa.CheckConstraint(
            "status IN ('pendente', 'parcialmente_paga', 'paga', 'cancelada')",
            name="ck_cobrancas_status_valido",
        ),
        sa.CheckConstraint("valor_total > 0", name="ck_cobrancas_valor_total_positivo"),
        sa.ForeignKeyConstraint(["cliente_id"], ["clientes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["proposta_id"], ["propostas.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("proposta_id", name="uq_cobrancas_proposta_id"),
        sa.UniqueConstraint("referencia_externa", name="uq_cobrancas_referencia_externa"),
    )
    op.create_index("ix_cobrancas_id", "cobrancas", ["id"])
    op.create_index("ix_cobrancas_proposta_id", "cobrancas", ["proposta_id"])
    op.create_index("ix_cobrancas_cliente_id", "cobrancas", ["cliente_id"])
    op.create_index("ix_cobrancas_status", "cobrancas", ["status"])

    op.create_table(
        "pagamentos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cobranca_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.String(length=20), nullable=False),
        sa.Column("valor", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("metodo", sa.String(length=30), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("provider_payment_id", sa.String(length=200), nullable=True),
        sa.Column("provider_reference", sa.String(length=200), nullable=True),
        sa.Column("aprovado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reembolsado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pendente', 'aprovado', 'recusado', 'cancelado', 'reembolsado')",
            name="ck_pagamentos_status_valido",
        ),
        sa.CheckConstraint(
            "tipo IN ('integral', 'entrada', 'saldo')",
            name="ck_pagamentos_tipo_valido",
        ),
        sa.CheckConstraint("valor > 0", name="ck_pagamentos_valor_positivo"),
        sa.ForeignKeyConstraint(["cobranca_id"], ["cobrancas.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_payment_id", name="uq_pagamentos_provider_payment_id"),
    )
    op.create_index("ix_pagamentos_id", "pagamentos", ["id"])
    op.create_index("ix_pagamentos_cobranca_id", "pagamentos", ["cobranca_id"])
    op.create_index("ix_pagamentos_status", "pagamentos", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pagamentos_status", table_name="pagamentos")
    op.drop_index("ix_pagamentos_cobranca_id", table_name="pagamentos")
    op.drop_index("ix_pagamentos_id", table_name="pagamentos")
    op.drop_table("pagamentos")
    op.drop_index("ix_cobrancas_status", table_name="cobrancas")
    op.drop_index("ix_cobrancas_cliente_id", table_name="cobrancas")
    op.drop_index("ix_cobrancas_proposta_id", table_name="cobrancas")
    op.drop_index("ix_cobrancas_id", table_name="cobrancas")
    op.drop_table("cobrancas")
