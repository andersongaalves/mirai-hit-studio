"""Audio tag versions, profiles and durable preview jobs; no historical backfill."""
import sqlalchemy as sa
from alembic import op

revision = "e8a0c2d4f679"
down_revision = "d7f9a1c3e568"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("producao_arquivos", sa.Column("original_restrito", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("producao_arquivos") as batch:
        batch.create_check_constraint("ck_producao_arquivos_original_tag_privado", "NOT original_restrito OR NOT visivel_cliente")
    op.create_table(
        "audio_tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("nome", sa.String(180), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("conteudo", sa.LargeBinary(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("duracao", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("length(sha256) = 64", name="ck_audio_tag_sha256"),
        sa.CheckConstraint("length(conteudo) BETWEEN 1 AND 2097152", name="ck_audio_tag_tamanho"),
        sa.CheckConstraint("duracao > 0 AND duracao <= 10", name="ck_audio_tag_duracao"),
    )
    op.create_table(
        "audio_tag_perfis",
        sa.Column("chave", sa.String(40), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("audio_tags.id", ondelete="RESTRICT")),
        sa.Column("intervalo_segundos", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("volume_percentual", sa.Integer(), nullable=False, server_default="40"),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint("intervalo_segundos BETWEEN 10 AND 120", name="ck_audio_tag_intervalo"),
        sa.CheckConstraint("volume_percentual BETWEEN 1 AND 100", name="ck_audio_tag_volume"),
        sa.CheckConstraint("versao >= 1", name="ck_audio_tag_perfil_versao"),
    )
    op.create_table(
        "previa_tag_jobs",
        sa.Column("arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("audio_tags.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("intervalo_segundos", sa.Integer(), nullable=False),
        sa.Column("volume_percentual", sa.Integer(), nullable=False),
        sa.Column("reserva_bytes", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(12), nullable=False, server_default="pendente"),
        sa.Column("object_key", sa.String(180), unique=True),
        sa.Column("sha256", sa.String(64)),
        sa.Column("tamanho_bytes", sa.Integer()),
        sa.Column("visivel_cliente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime(timezone=True)),
        sa.CheckConstraint("estado IN ('pendente', 'pronto', 'erro')", name="ck_previa_tag_estado"),
        sa.CheckConstraint("intervalo_segundos BETWEEN 10 AND 120", name="ck_previa_tag_intervalo"),
        sa.CheckConstraint("volume_percentual BETWEEN 1 AND 100", name="ck_previa_tag_volume"),
        sa.CheckConstraint("reserva_bytes BETWEEN 1 AND 52428800", name="ck_previa_tag_reserva"),
        sa.CheckConstraint("(estado <> 'pronto') OR (object_key IS NOT NULL AND sha256 IS NOT NULL AND tamanho_bytes > 0)",
                           name="ck_previa_tag_resultado"),
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in ("audio_tags", "audio_tag_perfis", "previa_tag_jobs"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            for role in ("anon", "authenticated"):
                op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                    REVOKE ALL ON public.{table} FROM {role}; END IF; END $$""")
        for role in ("anon", "authenticated"):
            op.execute(f"""DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN
                REVOKE ALL ON SEQUENCE public.audio_tags_id_seq FROM {role}; END IF; END $$""")


def downgrade():
    op.drop_table("previa_tag_jobs")
    op.drop_table("audio_tag_perfis")
    op.drop_table("audio_tags")
    with op.batch_alter_table("producao_arquivos") as batch:
        batch.drop_constraint("ck_producao_arquivos_original_tag_privado", type_="check")
        batch.drop_column("original_restrito")
