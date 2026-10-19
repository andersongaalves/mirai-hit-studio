"""Conserved credit allocations and append-only movements. No historical backfill."""
import sqlalchemy as sa
from alembic import op

revision = "a1c3e5f7b902"
down_revision = "f9b1d3e5a780"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "credito_alocacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("lote_id", sa.Integer(), sa.ForeignKey("credito_lotes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("cliente_id", sa.Integer(), sa.ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantidade", sa.Numeric(12, 3), nullable=False),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("snapshot_servico", sa.JSON(), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantidade > 0 AND quantidade <= 1000000", name="ck_credito_alocacao_quantidade"),
        sa.CheckConstraint("valor_centavos >= 0", name="ck_credito_alocacao_valor"),
        sa.CheckConstraint("length(motivo) >= 5", name="ck_credito_alocacao_motivo"),
    )
    op.create_index("ix_credito_alocacoes_lote_id", "credito_alocacoes", ["lote_id"])
    op.create_index("ix_credito_alocacoes_producao_id", "credito_alocacoes", ["producao_id"])
    op.create_table(
        "credito_movimentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alocacao_id", sa.Integer(), sa.ForeignKey("credito_alocacoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("motivo", sa.String(500), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False, unique=True),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("alocacao_id", "tipo", name="uq_credito_movimento_tipo"),
        sa.CheckConstraint("tipo IN ('reserva','consumo','devolucao','estorno')", name="ck_credito_movimento_tipo"),
        sa.CheckConstraint("length(motivo) >= 5", name="ck_credito_movimento_motivo"),
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in ("credito_alocacoes", "credito_movimentos"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            op.execute(f"""CREATE TRIGGER credito_registro_imutavel BEFORE UPDATE OR DELETE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION public.creditos_registro_imutavel()""")
            for role in ("anon", "authenticated"):
                op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    REVOKE ALL ON public.{table} FROM {role};
                    REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM {role}; END IF; END $$""")


def downgrade():
    op.drop_table("credito_movimentos")
    op.drop_index("ix_credito_alocacoes_producao_id", table_name="credito_alocacoes")
    op.drop_index("ix_credito_alocacoes_lote_id", table_name="credito_alocacoes")
    op.drop_table("credito_alocacoes")
