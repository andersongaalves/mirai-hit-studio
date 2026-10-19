"""Immutable origin of credit-funded contract stages; no historical backfill."""
import sqlalchemy as sa
from alembic import op

revision = "b3d5f7a9c014"
down_revision = "a1c3e5f7b902"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "credito_etapas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("etapa_id", sa.Integer(), sa.ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("alocacao_id", sa.Integer(), sa.ForeignKey("credito_alocacoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("ordem_no_item", sa.Integer(), nullable=False),
        sa.UniqueConstraint("alocacao_id", "ordem_no_item", name="uq_credito_etapa_origem"),
        sa.CheckConstraint("ordem_no_item > 0", name="ck_credito_etapa_ordem"),
    )
    op.create_index("ix_credito_etapas_alocacao_id", "credito_etapas", ["alocacao_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.credito_etapas ENABLE ROW LEVEL SECURITY")
        op.execute("""CREATE TRIGGER credito_registro_imutavel BEFORE UPDATE OR DELETE ON public.credito_etapas
            FOR EACH ROW EXECUTE FUNCTION public.creditos_registro_imutavel()""")
        for role in ("anon", "authenticated"):
            op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                REVOKE ALL ON public.credito_etapas FROM {role};
                REVOKE ALL ON SEQUENCE public.credito_etapas_id_seq FROM {role}; END IF; END $$""")


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM credito_etapas")).scalar_one():
        raise RuntimeError("credit_stage_records_prevent_downgrade")
    op.drop_index("ix_credito_etapas_alocacao_id", table_name="credito_etapas")
    op.drop_table("credito_etapas")
