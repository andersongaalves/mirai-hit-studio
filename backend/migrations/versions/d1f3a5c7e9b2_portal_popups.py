"""Pop-ups sent by the Admin to the client and producer portals.

Revision ID: d1f3a5c7e9b2
Revises: c9e1a3b5d7f2
"""
import sqlalchemy as sa
from alembic import op

revision = "d1f3a5c7e9b2"
down_revision = "c9e1a3b5d7f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_popups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("titulo", sa.String(80), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("publico", sa.String(10), nullable=False),
        sa.Column("tema", sa.String(12), nullable=False, server_default="ciano"),
        sa.Column("tamanho", sa.String(10), nullable=False, server_default="pequeno"),
        sa.Column("botao_rotulo", sa.String(40), nullable=True),
        sa.Column("botao_url", sa.String(300), nullable=True),
        sa.Column("frequencia", sa.String(12), nullable=False, server_default="uma_vez"),
        sa.Column("inicio", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fim", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("autor_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("publico IN ('cliente', 'produtor', 'todos')", name="ck_portal_popups_publico"),
        sa.CheckConstraint("tema IN ('ciano', 'roxo', 'amarelo', 'verde', 'vermelho')", name="ck_portal_popups_tema"),
        sa.CheckConstraint("tamanho IN ('pequeno', 'medio')", name="ck_portal_popups_tamanho"),
        sa.CheckConstraint("frequencia IN ('uma_vez', 'cada_sessao')", name="ck_portal_popups_frequencia"),
        sa.CheckConstraint("fim IS NULL OR inicio IS NULL OR fim > inicio", name="ck_portal_popups_periodo"),
    )
    op.create_table(
        "portal_popup_vistos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("popup_id", sa.Integer(), sa.ForeignKey("portal_popups.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("visto_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("popup_id", "usuario_id", name="uq_portal_popup_vistos_popup_usuario"),
    )
    op.create_index("ix_portal_popup_vistos_popup_id", "portal_popup_vistos", ["popup_id"])
    op.create_index("ix_portal_popup_vistos_usuario_id", "portal_popup_vistos", ["usuario_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in ("portal_popups", "portal_popup_vistos"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"""DO $$ BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                    REVOKE ALL ON public.{table} FROM anon;
                    REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM anon;
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                    REVOKE ALL ON public.{table} FROM authenticated;
                    REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM authenticated;
                END IF;
            END $$""")


def downgrade():
    op.drop_index("ix_portal_popup_vistos_usuario_id", table_name="portal_popup_vistos")
    op.drop_index("ix_portal_popup_vistos_popup_id", table_name="portal_popup_vistos")
    op.drop_table("portal_popup_vistos")
    op.drop_table("portal_popups")
