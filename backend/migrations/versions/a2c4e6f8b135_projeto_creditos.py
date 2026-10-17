"""Portfolio project credits (Roadmap 3.0, 5.19), no backfill.

Revision ID: a2c4e6f8b135
Revises: f3b5d7a9c124
"""
import sqlalchemy as sa
from alembic import op

revision = "a2c4e6f8b135"
down_revision = "f3b5d7a9c124"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "projeto_creditos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("projeto_id", sa.Integer(), sa.ForeignKey("projetos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("funcao", sa.String(20), nullable=False),
        sa.Column("funcao_outra", sa.String(60), nullable=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("projeto_id", "ordem", name="uq_projeto_credito_ordem"),
        sa.CheckConstraint(
            "funcao IN ('producao', 'mixagem', 'masterizacao', 'composicao', 'gravacao', 'beat', 'outra')",
            name="ck_projeto_credito_funcao",
        ),
        sa.CheckConstraint(
            "(funcao = 'outra' AND funcao_outra IS NOT NULL) OR (funcao <> 'outra' AND funcao_outra IS NULL)",
            name="ck_projeto_credito_funcao_outra",
        ),
        sa.CheckConstraint("ordem >= 1", name="ck_projeto_credito_ordem"),
    )
    op.create_index("ix_projeto_creditos_projeto_id", "projeto_creditos", ["projeto_id"])
    op.create_index("ix_projeto_creditos_usuario_id", "projeto_creditos", ["usuario_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.projeto_creditos ENABLE ROW LEVEL SECURITY")
        # Served only through the backend; Supabase client roles never read it directly.
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.projeto_creditos FROM anon;
                REVOKE ALL ON SEQUENCE public.projeto_creditos_id_seq FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.projeto_creditos FROM authenticated;
                REVOKE ALL ON SEQUENCE public.projeto_creditos_id_seq FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_index("ix_projeto_creditos_usuario_id", table_name="projeto_creditos")
    op.drop_index("ix_projeto_creditos_projeto_id", table_name="projeto_creditos")
    op.drop_table("projeto_creditos")
