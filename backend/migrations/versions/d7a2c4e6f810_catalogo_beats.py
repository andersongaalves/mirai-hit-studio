"""Catalogo interno de beats, permissao e licencas comerciais."""

import sqlalchemy as sa
from alembic import op

revision = "d7a2c4e6f810"
down_revision = "c4e6a8b0d125"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch:
        batch.add_column(
            sa.Column(
                "painel_beats", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        )
    op.create_table(
        "beats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "produtor_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(160), nullable=False),
        sa.Column("descricao", sa.Text(), server_default="", nullable=False),
        sa.Column("bpm", sa.Integer()),
        sa.Column("tonalidade", sa.String(24)),
        sa.Column("generos", sa.String(240), server_default="", nullable=False),
        sa.Column("preco_lease", sa.Numeric(12, 2)),
        sa.Column("preco_exclusivo", sa.Numeric(12, 2)),
        sa.Column("status", sa.String(16), server_default="revisao", nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "aplica_desconto", sa.Boolean(), server_default=sa.true(), nullable=False
        ),
        sa.Column("original_ref", sa.String(180), nullable=False, unique=True),
        sa.Column("original_sha256", sa.String(64), nullable=False),
        sa.Column("preview_ref", sa.String(180), nullable=False, unique=True),
        sa.Column("preview_sha256", sa.String(64), nullable=False),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column(
            "revisado_por_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
        ),
        sa.Column("revisado_em", sa.DateTime(timezone=True)),
        sa.Column("motivo_rejeicao", sa.String(500)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('revisao','aprovado','rejeitado','vendido')",
            name="ck_beats_status",
        ),
        sa.CheckConstraint(
            "preco_lease IS NULL OR preco_lease > 0", name="ck_beats_preco_lease"
        ),
        sa.CheckConstraint(
            "preco_exclusivo IS NULL OR preco_exclusivo > 0",
            name="ck_beats_preco_exclusivo",
        ),
        sa.CheckConstraint(
            "preco_lease IS NOT NULL OR preco_exclusivo IS NOT NULL",
            name="ck_beats_algum_preco",
        ),
        sa.CheckConstraint(
            "length(original_sha256) = 64 AND length(preview_sha256) = 64",
            name="ck_beats_hashes",
        ),
    )
    op.create_index("ix_beats_produtor_id", "beats", ["produtor_id"])
    op.create_index("ix_beats_status", "beats", ["status"])
    with op.batch_alter_table("orcamentos") as batch:
        batch.add_column(
            sa.Column(
                "beat_id",
                sa.Integer(),
                sa.ForeignKey(
                    "beats.id", ondelete="RESTRICT", name="fk_orcamentos_beat_id_beats"
                ),
                nullable=True,
            )
        )
        batch.add_column(sa.Column("licenca_beat", sa.String(12), nullable=True))
        batch.create_check_constraint(
            "ck_orcamentos_beat_licenca",
            "(beat_id IS NULL AND licenca_beat IS NULL) OR (beat_id IS NOT NULL AND licenca_beat IN ('lease','exclusivo'))",
        )
    op.create_index("ix_orcamentos_beat_id", "orcamentos", ["beat_id"])
    op.create_table(
        "beat_licencas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "beat_id",
            sa.Integer(),
            sa.ForeignKey("beats.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "proposta_id",
            sa.Integer(),
            sa.ForeignKey("propostas.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("clientes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("tipo", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), server_default="reservada", nullable=False),
        sa.Column("valor", sa.Numeric(12, 2), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("adquirida_em", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "proposta_id", "beat_id", "tipo", name="uq_beat_licenca_proposta_beat_tipo"
        ),
        sa.CheckConstraint(
            "tipo IN ('lease','exclusivo')", name="ck_beat_licencas_tipo"
        ),
        sa.CheckConstraint(
            "status IN ('reservada','adquirida','cancelada')",
            name="ck_beat_licencas_status",
        ),
        sa.CheckConstraint("valor > 0", name="ck_beat_licencas_valor"),
    )
    for col in ("beat_id", "proposta_id", "cliente_id"):
        op.create_index(f"ix_beat_licencas_{col}", "beat_licencas", [col])
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            "uq_beat_exclusivo_ativo",
            "beat_licencas",
            ["beat_id"],
            unique=True,
            postgresql_where=sa.text(
                "tipo='exclusivo' AND status IN ('reservada','adquirida')"
            ),
        )
        for table in ("beats", "beat_licencas"):
            op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
            for role in ("anon", "authenticated"):
                op.execute(
                    f"DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='{role}') THEN REVOKE ALL ON public.{table} FROM {role}; REVOKE ALL ON SEQUENCE public.{table}_id_seq FROM {role}; END IF; END $$"
                )


def downgrade():
    op.drop_index("ix_orcamentos_beat_id", table_name="orcamentos")
    with op.batch_alter_table("orcamentos") as batch:
        batch.drop_constraint("ck_orcamentos_beat_licenca", type_="check")
        batch.drop_column("licenca_beat")
        batch.drop_column("beat_id")
    op.drop_table("beat_licencas")
    op.drop_table("beats")
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_column("painel_beats")
