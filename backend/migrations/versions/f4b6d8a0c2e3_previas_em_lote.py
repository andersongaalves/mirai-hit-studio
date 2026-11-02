"""Regenerate every tagged preview in a queue: batches and per-item queue state.

Revision ID: f4b6d8a0c2e3
Revises: e3a5c7e9b1d4
"""
import sqlalchemy as sa
from alembic import op

revision = "f4b6d8a0c2e3"
down_revision = "e3a5c7e9b1d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "previa_lotes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("autor_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sem_tag", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("total >= 0 AND sem_tag >= 0", name="ck_previa_lotes_contagens"),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("previa_tag_jobs") as batch:
            batch.add_column(sa.Column("lote_id", sa.Integer(), nullable=True))
            batch.create_foreign_key("fk_previa_tag_jobs_lote", "previa_lotes", ["lote_id"], ["id"], ondelete="SET NULL")
        with op.batch_alter_table("beats") as batch:
            batch.add_column(sa.Column("previa_lote_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("previa_estado", sa.String(12), nullable=True))
            batch.create_foreign_key("fk_beats_previa_lote", "previa_lotes", ["previa_lote_id"], ["id"], ondelete="SET NULL")
            batch.create_check_constraint("ck_beats_previa_estado",
                                          "previa_estado IS NULL OR previa_estado IN ('pendente', 'pronto', 'erro')")
    else:
        op.add_column("previa_tag_jobs", sa.Column("lote_id", sa.Integer(), nullable=True))
        op.create_foreign_key("fk_previa_tag_jobs_lote", "previa_tag_jobs", "previa_lotes", ["lote_id"], ["id"],
                              ondelete="SET NULL")
        op.add_column("beats", sa.Column("previa_lote_id", sa.Integer(), nullable=True))
        op.add_column("beats", sa.Column("previa_estado", sa.String(12), nullable=True))
        op.create_foreign_key("fk_beats_previa_lote", "beats", "previa_lotes", ["previa_lote_id"], ["id"],
                              ondelete="SET NULL")
        op.create_check_constraint("ck_beats_previa_estado", "beats",
                                   "previa_estado IS NULL OR previa_estado IN ('pendente', 'pronto', 'erro')")
    op.create_index("ix_previa_tag_jobs_lote_id", "previa_tag_jobs", ["lote_id"])
    op.create_index("ix_beats_previa_estado", "beats", ["previa_estado"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE public.previa_lotes ENABLE ROW LEVEL SECURITY")
        op.execute("""DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN
                REVOKE ALL ON public.previa_lotes FROM anon;
                REVOKE ALL ON SEQUENCE public.previa_lotes_id_seq FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN
                REVOKE ALL ON public.previa_lotes FROM authenticated;
                REVOKE ALL ON SEQUENCE public.previa_lotes_id_seq FROM authenticated;
            END IF;
        END $$""")


def downgrade():
    op.drop_index("ix_beats_previa_estado", table_name="beats")
    op.drop_index("ix_previa_tag_jobs_lote_id", table_name="previa_tag_jobs")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("beats") as batch:
            batch.drop_constraint("ck_beats_previa_estado", type_="check")
            batch.drop_constraint("fk_beats_previa_lote", type_="foreignkey")
            batch.drop_column("previa_estado")
            batch.drop_column("previa_lote_id")
        with op.batch_alter_table("previa_tag_jobs") as batch:
            batch.drop_constraint("fk_previa_tag_jobs_lote", type_="foreignkey")
            batch.drop_column("lote_id")
    else:
        op.drop_constraint("ck_beats_previa_estado", "beats", type_="check")
        op.drop_constraint("fk_beats_previa_lote", "beats", type_="foreignkey")
        op.drop_column("beats", "previa_estado")
        op.drop_column("beats", "previa_lote_id")
        op.drop_constraint("fk_previa_tag_jobs_lote", "previa_tag_jobs", type_="foreignkey")
        op.drop_column("previa_tag_jobs", "lote_id")
    op.drop_table("previa_lotes")
