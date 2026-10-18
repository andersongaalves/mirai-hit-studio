"""Private producer portfolio submissions, without changing existing projects.

Revision ID: d7f9a1c3e568
Revises: b4d6f8a0c357
"""
import sqlalchemy as sa
from alembic import op

revision = "d7f9a1c3e568"
down_revision = "b4d6f8a0c357"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portfolio_envios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("produtor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT")),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("dados", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(12), nullable=False, server_default="pendente"),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("autorizado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revisado_em", sa.DateTime(timezone=True)),
        sa.Column("revisado_por", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT")),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projetos.id", ondelete="SET NULL"), unique=True),
        sa.Column("motivo", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("produtor_id", "request_id", name="uq_portfolio_envio_request"),
        sa.CheckConstraint("status IN ('pendente', 'aprovado', 'recusado')", name="ck_portfolio_envio_status"),
        sa.CheckConstraint("versao >= 1", name="ck_portfolio_envio_versao"),
        sa.CheckConstraint("autorizado_em IS NOT NULL", name="ck_portfolio_envio_consentimento"),
    )
    op.create_index("ix_portfolio_envios_produtor_id", "portfolio_envios", ["produtor_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.portfolio_envios ENABLE ROW LEVEL SECURITY")
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.portfolio_envios FROM anon;
                REVOKE ALL ON SEQUENCE public.portfolio_envios_id_seq FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.portfolio_envios FROM authenticated;
                REVOKE ALL ON SEQUENCE public.portfolio_envios_id_seq FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_index("ix_portfolio_envios_produtor_id", table_name="portfolio_envios")
    op.drop_table("portfolio_envios")
