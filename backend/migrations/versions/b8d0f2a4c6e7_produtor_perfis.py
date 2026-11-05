"""Public producer pages: what each producer customises on their profile.

Revision ID: b8d0f2a4c6e7
Revises: a6c8e0b2d4f5
"""
import sqlalchemy as sa
from alembic import op

revision = "b8d0f2a4c6e7"
down_revision = "a6c8e0b2d4f5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "produtor_perfis",
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("headline", sa.String(120), nullable=True),
        sa.Column("bio", sa.String(1500), nullable=True),
        sa.Column("cidade", sa.String(80), nullable=True),
        sa.Column("foto_url", sa.String(500), nullable=True),
        sa.Column("foto_ref", sa.String(500), nullable=True),
        sa.Column("capa_url", sa.String(500), nullable=True),
        sa.Column("capa_ref", sa.String(500), nullable=True),
        sa.Column("cor", sa.String(7), nullable=True),
        sa.Column("links_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("aba_inicial", sa.String(12), nullable=False, server_default="portfolio"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_produtor_perfis_slug"),
        sa.CheckConstraint("aba_inicial IN ('portfolio', 'beats')", name="ck_produtor_perfis_aba_inicial"),
        sa.CheckConstraint("cor IS NULL OR length(cor) = 7", name="ck_produtor_perfis_cor"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.produtor_perfis ENABLE ROW LEVEL SECURITY")
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.produtor_perfis FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.produtor_perfis FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_table("produtor_perfis")
