"""Mirai Hit Labs admin: releases, coupons and store content.

- plugin_versoes: release history per plugin (the update checker reads the latest stable).
- labs_cupons / labs_cupom_usos: discount codes and each purchase that used one.
- labs_conteudo: editable store blocks (announcement banner).

Revision ID: c6f8a0b2d4e5
Revises: b5e7a9c1d3f4
"""
import sqlalchemy as sa
from alembic import op

revision = "c6f8a0b2d4e5"
down_revision = "b5e7a9c1d3f4"
branch_labels = None
depends_on = None

TABLES = ("plugin_versoes", "labs_cupons", "labs_cupom_usos", "labs_conteudo")


def upgrade():
    op.create_table(
        "plugin_versoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("versao", sa.String(20), nullable=False),
        sa.Column("canal", sa.String(10), nullable=False, server_default="estavel"),
        sa.Column("notas", sa.Text(), nullable=True),
        sa.Column("notas_en", sa.Text(), nullable=True),
        sa.Column("obrigatoria", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("publicada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plugin_id", "versao", name="uq_plugin_versoes_plugin_versao"),
        sa.CheckConstraint("canal IN ('estavel','beta')", name="ck_plugin_versoes_canal"),
    )
    op.create_index("ix_plugin_versoes_plugin_id", "plugin_versoes", ["plugin_id"])

    op.create_table(
        "labs_cupons",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("codigo", sa.String(32), nullable=False),
        sa.Column("descricao", sa.String(160), nullable=True),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=True),
        sa.Column("valido_de", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valido_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_usos", sa.Integer(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("codigo", name="uq_labs_cupons_codigo"),
        sa.CheckConstraint("tipo IN ('percentual','valor')", name="ck_labs_cupons_tipo"),
        sa.CheckConstraint(
            "(tipo = 'percentual' AND valor > 0 AND valor <= 100) OR (tipo = 'valor' AND valor > 0)",
            name="ck_labs_cupons_valor",
        ),
        sa.CheckConstraint("max_usos IS NULL OR max_usos > 0", name="ck_labs_cupons_max_usos"),
        sa.CheckConstraint("valido_ate IS NULL OR valido_de IS NULL OR valido_ate > valido_de",
                           name="ck_labs_cupons_periodo"),
    )
    op.create_index("ix_labs_cupons_plugin_id", "labs_cupons", ["plugin_id"])

    op.create_table(
        "labs_cupom_usos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cupom_id", sa.Integer(), sa.ForeignKey("labs_cupons.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("licenca_id", sa.Integer(), sa.ForeignKey("plugin_licencas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("orcamento_id", sa.Integer(), sa.ForeignKey("orcamentos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pedido_stripe_id", sa.Integer(), sa.ForeignKey("plugin_pedidos_stripe.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("moeda", sa.String(3), nullable=False, server_default="brl"),
        sa.Column("desconto", sa.Numeric(12, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("orcamento_id", name="uq_labs_cupom_usos_orcamento"),
        sa.UniqueConstraint("pedido_stripe_id", name="uq_labs_cupom_usos_pedido_stripe"),
        sa.CheckConstraint("desconto >= 0", name="ck_labs_cupom_usos_desconto"),
    )
    op.create_index("ix_labs_cupom_usos_cupom_id", "labs_cupom_usos", ["cupom_id"])
    op.create_index("ix_labs_cupom_usos_cliente_id", "labs_cupom_usos", ["cliente_id"])
    op.create_index("ix_labs_cupom_usos_licenca_id", "labs_cupom_usos", ["licenca_id"])

    op.create_table(
        "labs_conteudo",
        sa.Column("chave", sa.String(40), primary_key=True),
        sa.Column("dados_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Existing plugins start their history with the version they already show.
    op.execute("""
        INSERT INTO plugin_versoes (plugin_id, versao, canal, publicada_em)
        SELECT id, versao, 'estavel', COALESCE(publicado_em, created_at)
        FROM plugins WHERE versao IS NOT NULL AND versao <> ''
    """)

    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                    REVOKE ALL ON public.{table} FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                    REVOKE ALL ON public.{table} FROM authenticated;
                END IF;
            END $$""")


def downgrade():
    op.drop_table("labs_conteudo")
    op.drop_table("labs_cupom_usos")
    op.drop_table("labs_cupons")
    op.drop_table("plugin_versoes")
