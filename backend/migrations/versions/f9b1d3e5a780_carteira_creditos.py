"""Service-credit contracts, immutable economic lots and acquisition ledger. No backfill."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f9b1d3e5a780"
down_revision = "e8a0c2d4f679"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.add_column("servicos", sa.Column("credito_servico", json_type, nullable=True))
    op.add_column("propostas", sa.Column("finalidade", sa.String(12), nullable=False, server_default="producao"))
    op.add_column("propostas", sa.Column("contrato_creditos", json_type, nullable=True))
    with op.batch_alter_table("propostas") as batch:
        batch.create_check_constraint("ck_propostas_finalidade", "finalidade IN ('producao','creditos')")
    op.create_table(
        "credito_contrato_itens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("proposta_id", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("proposta_versao", sa.Integer(), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("servico_nome", sa.String(100), nullable=False),
        sa.Column("linha", sa.Integer(), nullable=False),
        sa.Column("componente", sa.Integer(), nullable=False),
        sa.Column("unidade", sa.String(10), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("contrato_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("proposta_id", "proposta_versao", "linha", "componente", name="uq_credito_contrato_origem"),
        sa.CheckConstraint("unidade IN ('faixa','canal','hora')", name="ck_credito_contrato_unidade"),
        sa.CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_contrato_quantidade"),
        sa.CheckConstraint("unidade = 'hora' OR quantidade = floor(quantidade)", name="ck_credito_contrato_discreto"),
        sa.CheckConstraint("valor_centavos >= 0 AND proposta_versao > 0 AND linha > 0 AND componente >= 0", name="ck_credito_contrato_origem_valor"),
        sa.CheckConstraint("length(contrato_sha256) = 64", name="ck_credito_contrato_hash"),
    )
    op.create_table(
        "credito_lotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("contrato_item_id", sa.Integer(), sa.ForeignKey("credito_contrato_itens.id", ondelete="RESTRICT"), nullable=False, unique=True),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cobranca_id", sa.Integer(), sa.ForeignKey("cobrancas.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("servico_id", sa.Integer(), sa.ForeignKey("servicos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("servico_nome", sa.String(100), nullable=False),
        sa.Column("linha", sa.Integer(), nullable=False),
        sa.Column("componente", sa.Integer(), nullable=False),
        sa.Column("unidade", sa.String(10), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("contrato_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("cobranca_id", "linha", "componente", name="uq_credito_lote_origem"),
        sa.CheckConstraint("unidade IN ('faixa','canal','hora')", name="ck_credito_lote_unidade"),
        sa.CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_lote_quantidade"),
        sa.CheckConstraint("unidade = 'hora' OR quantidade = floor(quantidade)", name="ck_credito_lote_discreto"),
        sa.CheckConstraint("valor_centavos >= 0 AND linha > 0 AND componente >= 0", name="ck_credito_lote_origem_valor"),
        sa.CheckConstraint("length(contrato_sha256) = 64", name="ck_credito_lote_contrato_hash"),
    )
    op.create_index("ix_credito_lotes_cliente_id", "credito_lotes", ["cliente_id"])
    op.create_table(
        "credito_lancamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("credito_lotes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("lote_id", name="uq_credito_aquisicao_lote"),
        sa.CheckConstraint("tipo = 'aquisicao'", name="ck_credito_lancamento_tipo"),
        sa.CheckConstraint("quantidade > 0", name="ck_credito_lancamento_quantidade"),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""CREATE FUNCTION public.creditos_registro_imutavel() RETURNS trigger
            LANGUAGE plpgsql SET search_path=pg_catalog AS $$ BEGIN
            RAISE EXCEPTION 'credit_record_is_immutable'; END $$""")
        op.execute("REVOKE ALL ON FUNCTION public.creditos_registro_imutavel() FROM PUBLIC")
        for table in ("credito_contrato_itens", "credito_lotes", "credito_lancamentos"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"""CREATE TRIGGER credito_registro_imutavel BEFORE UPDATE OR DELETE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION public.creditos_registro_imutavel()""")
            for role in ("anon", "authenticated"):
                op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    REVOKE ALL ON public.{table} FROM {role};
                    REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM {role}; END IF; END $$""")


def downgrade():
    for table in ("credito_lancamentos", "credito_lotes", "credito_contrato_itens"):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("credit_acquisition_history_prevents_downgrade")
    if op.get_bind().execute(sa.text(
        "SELECT 1 FROM propostas WHERE finalidade = 'creditos' OR contrato_creditos IS NOT NULL LIMIT 1"
    )).first():
        raise RuntimeError("credit_contract_history_prevents_downgrade")
    op.drop_table("credito_lancamentos")
    op.drop_index("ix_credito_lotes_cliente_id", table_name="credito_lotes")
    op.drop_table("credito_lotes")
    op.drop_table("credito_contrato_itens")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP FUNCTION public.creditos_registro_imutavel()")
    with op.batch_alter_table("propostas") as batch:
        batch.drop_constraint("ck_propostas_finalidade", type_="check")
        batch.drop_column("contrato_creditos")
        batch.drop_column("finalidade")
    op.drop_column("servicos", "credito_servico")
