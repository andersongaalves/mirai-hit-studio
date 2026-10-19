"""Freeze the producer economic pool of future credit reservations, without backfill."""
import sqlalchemy as sa
from alembic import op

revision = "c4e6a8b0d125"
down_revision = "b3d5f7a9c014"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("credito_alocacoes") as batch:
        batch.add_column(sa.Column("produtor_centavos", sa.Integer(), nullable=True))
        batch.create_check_constraint("ck_credito_alocacao_produtor",
            "produtor_centavos IS NULL OR (produtor_centavos >= 0 AND produtor_centavos <= valor_centavos)")
    op.create_table("repasse_etapas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("etapa_id", sa.Integer(), sa.ForeignKey("producao_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("produtor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bruto_centavos", sa.BigInteger(), nullable=False),
        sa.Column("produtor_centavos", sa.BigInteger(), nullable=False),
        sa.Column("mirai_centavos", sa.BigInteger(), nullable=False),
        sa.Column("origem_sha256", sa.String(64), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("bruto_centavos > 0 AND produtor_centavos >= 0 AND mirai_centavos >= 0 "
                           "AND produtor_centavos + mirai_centavos = bruto_centavos", name="ck_repasse_etapa_centavos"))
    for column in ("producao_id", "produtor_id"):
        op.create_index(f"ix_repasse_etapas_{column}", "repasse_etapas", [column])
    op.create_table("repasse_etapa_pagamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("repasse_id", sa.Integer(), sa.ForeignKey("repasse_etapas.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("referencia", sa.String(160), nullable=False),
        sa.Column("comprovante_arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), nullable=True, unique=True),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    if op.get_bind().dialect.name == "postgresql":
        for table in ("repasse_etapas", "repasse_etapa_pagamentos"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"""CREATE TRIGGER credito_registro_imutavel BEFORE UPDATE OR DELETE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION public.creditos_registro_imutavel()""")
            for role in ("anon", "authenticated"):
                op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    REVOKE ALL ON public.{table} FROM {role};
                    REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM {role}; END IF; END $$""")


def downgrade():
    for table in ("repasse_etapa_pagamentos", "repasse_etapas"):
        if op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar_one():
            raise RuntimeError("stage_payout_history_prevents_downgrade")
    if op.get_bind().execute(sa.text("SELECT count(*) FROM credito_alocacoes WHERE produtor_centavos IS NOT NULL")).scalar_one():
        raise RuntimeError("credit_payout_basis_prevents_downgrade")
    op.drop_table("repasse_etapa_pagamentos")
    op.drop_table("repasse_etapas")
    with op.batch_alter_table("credito_alocacoes") as batch:
        batch.drop_constraint("ck_credito_alocacao_produtor", type_="check")
        batch.drop_column("produtor_centavos")
