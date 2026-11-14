"""Mirai Hit Labs: international purchases with Stripe (English store, prices in USD).

- plugin_pedidos_stripe: one order per Stripe Checkout session; the reserved license
  becomes active when Stripe confirms the payment (webhook or the buyer's return).
- plugin_licencas.origem gains 'stripe'. Like 'compra', a Stripe license belongs to its
  order, so it stays out of the one-free/courtesy-license-per-client index.

Revision ID: b5e7a9c1d3f4
Revises: a4d6f8b0c2e3
"""
import sqlalchemy as sa
from alembic import op

revision = "b5e7a9c1d3f4"
down_revision = "a4d6f8b0c2e3"
branch_labels = None
depends_on = None

ORIGENS = "origem IN ('compra','gratuito','cortesia','stripe')"
ORIGENS_OLD = "origem IN ('compra','gratuito','cortesia')"


def _license_index(where):
    op.create_index(
        "uq_plugin_licencas_cliente_sem_compra",
        "plugin_licencas",
        ["plugin_id", "cliente_id"],
        unique=True,
        postgresql_where=sa.text(where),
        sqlite_where=sa.text(where),
    )


def upgrade():
    op.drop_index("uq_plugin_licencas_cliente_sem_compra", table_name="plugin_licencas")
    with op.batch_alter_table("plugin_licencas") as batch:
        batch.drop_constraint("ck_plugin_licencas_origem", type_="check")
        batch.create_check_constraint("ck_plugin_licencas_origem", ORIGENS)
    _license_index("origem NOT IN ('compra','stripe')")

    op.create_table(
        "plugin_pedidos_stripe",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("licenca_id", sa.Integer(), sa.ForeignKey("plugin_licencas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("moeda", sa.String(3), nullable=False, server_default="usd"),
        sa.Column("status", sa.String(12), nullable=False, server_default="aberto"),
        sa.Column("idempotency_key", sa.String(64), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent", sa.String(255), nullable=True),
        sa.Column("checkout_url", sa.String(1000), nullable=True),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pago_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("licenca_id", name="uq_plugin_pedidos_stripe_licenca"),
        sa.UniqueConstraint("idempotency_key", name="uq_plugin_pedidos_stripe_idempotency"),
        sa.UniqueConstraint("stripe_session_id", name="uq_plugin_pedidos_stripe_session"),
        sa.CheckConstraint("valor > 0", name="ck_plugin_pedidos_stripe_valor"),
        sa.CheckConstraint("moeda = 'usd'", name="ck_plugin_pedidos_stripe_moeda"),
        sa.CheckConstraint(
            "status IN ('aberto','pago','expirado','reembolsado','contestado')", name="ck_plugin_pedidos_stripe_status"
        ),
    )
    op.create_index("ix_plugin_pedidos_stripe_plugin_id", "plugin_pedidos_stripe", ["plugin_id"])
    op.create_index("ix_plugin_pedidos_stripe_cliente_id", "plugin_pedidos_stripe", ["cliente_id"])
    op.create_index("ix_plugin_pedidos_stripe_usuario_id", "plugin_pedidos_stripe", ["usuario_id"])
    op.create_index("ix_plugin_pedidos_stripe_stripe_payment_intent", "plugin_pedidos_stripe", ["stripe_payment_intent"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.plugin_pedidos_stripe ENABLE ROW LEVEL SECURITY")
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.plugin_pedidos_stripe FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.plugin_pedidos_stripe FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_table("plugin_pedidos_stripe")
    op.drop_index("uq_plugin_licencas_cliente_sem_compra", table_name="plugin_licencas")
    with op.batch_alter_table("plugin_licencas") as batch:
        batch.drop_constraint("ck_plugin_licencas_origem", type_="check")
        batch.create_check_constraint("ck_plugin_licencas_origem", ORIGENS_OLD)
    _license_index("origem <> 'compra'")
