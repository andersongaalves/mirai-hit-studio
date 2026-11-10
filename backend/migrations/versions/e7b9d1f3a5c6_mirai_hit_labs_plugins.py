"""Mirai Hit Labs: plugins, installers, licenses and plugin orders.

Revision ID: e7b9d1f3a5c6
Revises: c9e1a3b5d7f8
"""
import sqlalchemy as sa
from alembic import op

revision = "e7b9d1f3a5c6"
down_revision = "c9e1a3b5d7f8"
branch_labels = None
depends_on = None

TABLES = ("plugins", "plugin_arquivos", "plugin_licencas")


def upgrade():
    op.create_table(
        "plugins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(60), nullable=False),
        sa.Column("nome", sa.String(80), nullable=False),
        sa.Column("tagline", sa.String(160), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("categoria", sa.String(40), nullable=True),
        sa.Column("versao", sa.String(20), nullable=True),
        sa.Column("formatos_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("recursos_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("requisitos", sa.Text(), nullable=True),
        sa.Column("preco", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("preco_promocional", sa.Numeric(12, 2), nullable=True),
        sa.Column("capa_url", sa.String(500), nullable=True),
        sa.Column("capa_ref", sa.String(500), nullable=True),
        sa.Column("video_url", sa.String(300), nullable=True),
        sa.Column("status", sa.String(12), nullable=False, server_default="rascunho"),
        sa.Column("destaque", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("publicado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_plugins_slug"),
        sa.CheckConstraint("status IN ('rascunho','publicado','arquivado')", name="ck_plugins_status"),
        sa.CheckConstraint("preco >= 0", name="ck_plugins_preco"),
        sa.CheckConstraint(
            "preco_promocional IS NULL OR (preco_promocional >= 0 AND preco_promocional < preco)",
            name="ck_plugins_preco_promocional",
        ),
    )
    op.create_table(
        "plugin_arquivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sistema", sa.String(10), nullable=False),
        sa.Column("versao", sa.String(20), nullable=True),
        sa.Column("nome_arquivo", sa.String(160), nullable=True),
        sa.Column("arquivo_ref", sa.String(500), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("mime", sa.String(100), nullable=True),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=True),
        sa.Column("link_externo", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plugin_id", "sistema", name="uq_plugin_arquivos_plugin_sistema"),
        sa.CheckConstraint("sistema IN ('windows','macos')", name="ck_plugin_arquivos_sistema"),
        sa.CheckConstraint(
            "(arquivo_ref IS NOT NULL AND sha256 IS NOT NULL AND link_externo IS NULL) OR "
            "(arquivo_ref IS NULL AND sha256 IS NULL AND link_externo IS NOT NULL)",
            name="ck_plugin_arquivos_origem",
        ),
    )
    op.create_index("ix_plugin_arquivos_plugin_id", "plugin_arquivos", ["plugin_id"])
    op.create_index("uq_plugin_arquivos_ref", "plugin_arquivos", ["arquivo_ref"], unique=True)
    op.create_table(
        "plugin_licencas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("plugin_id", sa.Integer(), sa.ForeignKey("plugins.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposta_id", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("origem", sa.String(10), nullable=False, server_default="compra"),
        sa.Column("status", sa.String(10), nullable=False, server_default="reservada"),
        sa.Column("chave", sa.String(32), nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("ativada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("encerrada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("motivo", sa.String(40), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chave", name="uq_plugin_licencas_chave"),
        sa.UniqueConstraint("proposta_id", "plugin_id", name="uq_plugin_licencas_proposta_plugin"),
        sa.CheckConstraint(
            "status IN ('reservada','ativa','cancelada','revogada')", name="ck_plugin_licencas_status"
        ),
        sa.CheckConstraint("valor >= 0", name="ck_plugin_licencas_valor"),
        sa.CheckConstraint("origem IN ('compra','gratuito','cortesia')", name="ck_plugin_licencas_origem"),
        sa.CheckConstraint(
            "(origem = 'compra' AND proposta_id IS NOT NULL) OR (origem <> 'compra' AND proposta_id IS NULL)",
            name="ck_plugin_licencas_proposta",
        ),
    )
    op.create_index("ix_plugin_licencas_plugin_id", "plugin_licencas", ["plugin_id"])
    op.create_index("ix_plugin_licencas_cliente_id", "plugin_licencas", ["cliente_id"])
    op.create_index("ix_plugin_licencas_proposta_id", "plugin_licencas", ["proposta_id"])
    op.create_index(
        "uq_plugin_licencas_cliente_sem_compra",
        "plugin_licencas",
        ["plugin_id", "cliente_id"],
        unique=True,
        postgresql_where=sa.text("origem <> 'compra'"),
        sqlite_where=sa.text("origem <> 'compra'"),
    )

    with op.batch_alter_table("orcamentos") as batch:
        batch.add_column(sa.Column("plugin_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_orcamentos_plugin_id_plugins", "plugins", ["plugin_id"], ["id"], ondelete="RESTRICT"
        )
        batch.create_index("ix_orcamentos_plugin_id", ["plugin_id"])
        batch.create_check_constraint("ck_orcamentos_beat_ou_plugin", "beat_id IS NULL OR plugin_id IS NULL")
    with op.batch_alter_table("propostas") as batch:
        batch.drop_constraint("ck_propostas_finalidade", type_="check")
        batch.create_check_constraint(
            "ck_propostas_finalidade", "finalidade IN ('producao','creditos','plugins')"
        )

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
    with op.batch_alter_table("propostas") as batch:
        batch.drop_constraint("ck_propostas_finalidade", type_="check")
        batch.create_check_constraint("ck_propostas_finalidade", "finalidade IN ('producao','creditos')")
    with op.batch_alter_table("orcamentos") as batch:
        batch.drop_constraint("ck_orcamentos_beat_ou_plugin", type_="check")
        batch.drop_index("ix_orcamentos_plugin_id")
        batch.drop_constraint("fk_orcamentos_plugin_id_plugins", type_="foreignkey")
        batch.drop_column("plugin_id")
    op.drop_table("plugin_licencas")
    op.drop_table("plugin_arquivos")
    op.drop_table("plugins")
