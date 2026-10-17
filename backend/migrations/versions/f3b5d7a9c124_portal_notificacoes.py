"""Private per-user portal notifications, no historical backfill.

Revision ID: f3b5d7a9c124
Revises: f1a3c5e7b902
"""
import sqlalchemy as sa
from alembic import op

revision = "f3b5d7a9c124"
down_revision = "f1a3c5e7b902"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_notificacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("papel", sa.String(10), nullable=False),
        sa.Column("chave_evento", sa.String(180), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("proposta_id", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("vista_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("usuario_id", "chave_evento", name="uq_portal_notificacao_usuario_evento"),
        sa.CheckConstraint("papel IN ('cliente', 'produtor')", name="ck_portal_notificacao_papel"),
        sa.CheckConstraint("producao_id IS NOT NULL OR proposta_id IS NOT NULL", name="ck_portal_notificacao_contexto"),
    )
    op.create_index("ix_portal_notificacao_usuario_vista_id", "portal_notificacoes", ["usuario_id", "vista_em", "id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.portal_notificacoes ENABLE ROW LEVEL SECURITY")
        # The backend uses its database role; Supabase client roles never access this table directly.
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.portal_notificacoes FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.portal_notificacoes FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_table("portal_notificacoes")
