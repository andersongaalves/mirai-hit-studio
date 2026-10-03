"""create producer portal files and payouts

Revision ID: 24ef7f883a03
Revises: d3b8e1f4a720
Create Date: 2026-10-03 06:55:31.167756

"""

import sqlalchemy as sa

from alembic import op

revision = "24ef7f883a03"
down_revision = "d3b8e1f4a720"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "producao_arquivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "producao_id",
            sa.Integer(),
            sa.ForeignKey("producoes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "remetente_usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("nome_exibicao", sa.String(180), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(180), nullable=False),
        sa.Column("grupo_versao", sa.String(36), nullable=False),
        sa.Column("versao", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "substitui_arquivo_id",
            sa.Integer(),
            sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "visivel_produtor",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "visivel_cliente",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "tipo IN ('material', 'referencia', 'previa', 'entrega', 'comprovante')",
            name="ck_producao_arquivos_tipo_valido",
        ),
        sa.CheckConstraint(
            "tamanho_bytes > 0 AND tamanho_bytes <= 52428800",
            name="ck_producao_arquivos_tamanho_valido",
        ),
        sa.CheckConstraint(
            "length(sha256) = 64",
            name="ck_producao_arquivos_sha256_valido",
        ),
        sa.CheckConstraint(
            "versao > 0",
            name="ck_producao_arquivos_versao_positiva",
        ),
        sa.CheckConstraint(
            "substitui_arquivo_id IS NULL OR substitui_arquivo_id <> id",
            name="ck_producao_arquivos_substituicao_distinta",
        ),
        sa.UniqueConstraint("object_key", name="uq_producao_arquivos_object_key"),
        sa.UniqueConstraint(
            "grupo_versao",
            "versao",
            name="uq_producao_arquivos_grupo_versao",
        ),
        sa.UniqueConstraint(
            "substitui_arquivo_id",
            name="uq_producao_arquivos_substitui_arquivo_id",
        ),
    )
    op.create_index(
        "ix_producao_arquivos_producao_id",
        "producao_arquivos",
        ["producao_id"],
    )
    op.create_index(
        "ix_producao_arquivos_remetente_usuario_id",
        "producao_arquivos",
        ["remetente_usuario_id"],
    )
    op.create_index(
        "ix_producao_arquivos_tipo",
        "producao_arquivos",
        ["tipo"],
    )
    op.create_index(
        "ix_producao_arquivos_grupo_versao",
        "producao_arquivos",
        ["grupo_versao"],
    )

    op.create_table(
        "repasses_produtor",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "producao_id",
            sa.Integer(),
            sa.ForeignKey("producoes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "produtor_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("valor_combinado", sa.Numeric(12, 2), nullable=False),
        sa.Column("moeda", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("status", sa.String(20), nullable=False, server_default="definido"),
        sa.Column("liberado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pago_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("referencia_pagamento", sa.String(160), nullable=True),
        sa.Column(
            "comprovante_arquivo_id",
            sa.Integer(),
            sa.ForeignKey("producao_arquivos.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "valor_combinado > 0",
            name="ck_repasses_produtor_valor_positivo",
        ),
        sa.CheckConstraint(
            "moeda = 'BRL'",
            name="ck_repasses_produtor_moeda_brl",
        ),
        sa.CheckConstraint(
            "status IN ('definido', 'liberado', 'pago')",
            name="ck_repasses_produtor_status_valido",
        ),
        sa.CheckConstraint(
            "(status = 'definido' AND liberado_em IS NULL AND pago_em IS NULL) OR "
            "(status = 'liberado' AND liberado_em IS NOT NULL AND pago_em IS NULL) OR "
            "(status = 'pago' AND liberado_em IS NOT NULL AND pago_em IS NOT NULL)",
            name="ck_repasses_produtor_datas_coerentes",
        ),
        sa.UniqueConstraint("producao_id", name="uq_repasses_produtor_producao_id"),
        sa.UniqueConstraint(
            "comprovante_arquivo_id",
            name="uq_repasses_produtor_comprovante_arquivo_id",
        ),
    )
    op.create_index(
        "ix_repasses_produtor_produtor_id",
        "repasses_produtor",
        ["produtor_id"],
    )
    op.create_index(
        "ix_repasses_produtor_status",
        "repasses_produtor",
        ["status"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in ("producao_arquivos", "repasses_produtor"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            for role in ("anon", "authenticated"):
                op.execute(
                    "DO $$ BEGIN IF EXISTS "
                    f"(SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                    f"THEN REVOKE ALL ON TABLE {table} FROM {role}; "
                    "END IF; END; $$"
                )


def downgrade():
    op.drop_table("repasses_produtor")
    op.drop_table("producao_arquivos")
