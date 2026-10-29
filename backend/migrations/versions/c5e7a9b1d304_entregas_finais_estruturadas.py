"""Structured production final-delivery packages.

Revision ID: c5e7a9b1d304
Revises: b4d6f8a0c2e5
"""

import sqlalchemy as sa
from alembic import op

revision = "c5e7a9b1d304"
down_revision = "b4d6f8a0c2e5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "producao_entregas_finais",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("produtor_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("titulo", sa.String(150), nullable=False),
        sa.Column("arquivo_principal_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("wav_arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT")),
        sa.Column("multitrack_arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT")),
        sa.Column("multitrack_url", sa.String(2000)),
        sa.Column("licenca_arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT")),
        sa.Column("observacao", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("categoria IN ('instrumental', 'outro')", name="ck_entregas_finais_categoria"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_entregas_finais_request_hash"),
        sa.CheckConstraint("multitrack_arquivo_id IS NULL OR multitrack_url IS NULL", name="ck_entregas_finais_multitrack_origem_unica"),
        sa.CheckConstraint(
            "categoria <> 'instrumental' OR (wav_arquivo_id IS NOT NULL AND licenca_arquivo_id IS NOT NULL "
            "AND ((multitrack_arquivo_id IS NOT NULL) <> (multitrack_url IS NOT NULL)))",
            name="ck_entregas_finais_instrumental_completo",
        ),
        sa.UniqueConstraint("request_id", name="uq_entregas_finais_request_id"),
        sa.UniqueConstraint("arquivo_principal_id", name="uq_entregas_finais_principal"),
        sa.UniqueConstraint("wav_arquivo_id", name="uq_entregas_finais_wav"),
        sa.UniqueConstraint("multitrack_arquivo_id", name="uq_entregas_finais_multitrack"),
        sa.UniqueConstraint("licenca_arquivo_id", name="uq_entregas_finais_licenca"),
    )
    op.create_index("ix_entregas_finais_producao", "producao_entregas_finais", ["producao_id"])
    op.create_index("ix_entregas_finais_produtor", "producao_entregas_finais", ["produtor_id"])


def downgrade():
    op.drop_index("ix_entregas_finais_produtor", table_name="producao_entregas_finais")
    op.drop_index("ix_entregas_finais_producao", table_name="producao_entregas_finais")
    op.drop_table("producao_entregas_finais")
