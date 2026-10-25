"""Admin notifications and beat/request/portfolio contexts (AUD6-S11-001/002, AUD6-S04-002).

Revision ID: c6e8a0b2d4f1
Revises: b5d7f9a1c328
"""
import sqlalchemy as sa
from alembic import op

revision = "c6e8a0b2d4f1"
down_revision = "b5d7f9a1c328"
branch_labels = None
depends_on = None

OLD_ROLES = "papel IN ('cliente', 'produtor')"
NEW_ROLES = "papel IN ('cliente', 'produtor', 'admin')"
OLD_CONTEXT = "producao_id IS NOT NULL OR proposta_id IS NOT NULL"
NEW_CONTEXT = (
    "producao_id IS NOT NULL OR proposta_id IS NOT NULL OR beat_id IS NOT NULL "
    "OR orcamento_id IS NOT NULL OR portfolio_envio_id IS NOT NULL"
)
NEW_COLUMNS = (
    ("beat_id", "beats"),
    ("orcamento_id", "orcamentos"),
    ("portfolio_envio_id", "portfolio_envios"),
)


def _sqlite_table(*, extended):
    # SQLite cannot alter CHECK constraints in place; batch mode rebuilds the table from this definition.
    columns = [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("papel", sa.String(10), nullable=False),
        sa.Column("chave_evento", sa.String(180), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("proposta_id", sa.Integer(), sa.ForeignKey("propostas.id", ondelete="CASCADE"), nullable=True),
        sa.Column("arquivo_id", sa.Integer(), sa.ForeignKey("producao_arquivos.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("vista_em", sa.DateTime(timezone=True), nullable=True),
    ]
    if extended:
        columns += [
            sa.Column(name, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=True)
            for name, table in NEW_COLUMNS
        ]
    return sa.Table(
        "portal_notificacoes",
        sa.MetaData(),
        *columns,
        sa.UniqueConstraint("usuario_id", "chave_evento", name="uq_portal_notificacao_usuario_evento"),
        sa.CheckConstraint(NEW_ROLES if extended else OLD_ROLES, name="ck_portal_notificacao_papel"),
        sa.CheckConstraint(NEW_CONTEXT if extended else OLD_CONTEXT, name="ck_portal_notificacao_contexto"),
        sa.Index("ix_portal_notificacao_usuario_vista_id", "usuario_id", "vista_em", "id"),
    )


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("portal_notificacoes", recreate="always",
                                  copy_from=_sqlite_table(extended=False)) as batch:
            batch.drop_constraint("ck_portal_notificacao_papel", type_="check")
            batch.drop_constraint("ck_portal_notificacao_contexto", type_="check")
            for name, table in NEW_COLUMNS:
                batch.add_column(sa.Column(
                    name, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=True))
            batch.create_check_constraint("ck_portal_notificacao_papel", NEW_ROLES)
            batch.create_check_constraint("ck_portal_notificacao_contexto", NEW_CONTEXT)
        return
    for name, table in NEW_COLUMNS:
        op.add_column("portal_notificacoes", sa.Column(
            name, sa.Integer(), sa.ForeignKey(f"{table}.id", ondelete="CASCADE"), nullable=True))
        op.create_index(f"ix_portal_notificacao_{name}", "portal_notificacoes", [name])
    op.execute("ALTER TABLE portal_notificacoes DROP CONSTRAINT ck_portal_notificacao_papel")
    op.execute(f"ALTER TABLE portal_notificacoes ADD CONSTRAINT ck_portal_notificacao_papel CHECK ({NEW_ROLES})")
    op.execute("ALTER TABLE portal_notificacoes DROP CONSTRAINT ck_portal_notificacao_contexto")
    op.execute(f"ALTER TABLE portal_notificacoes ADD CONSTRAINT ck_portal_notificacao_contexto CHECK ({NEW_CONTEXT})")


def downgrade():
    # Rows that only exist under the new contexts cannot satisfy the old constraints.
    op.execute(
        "DELETE FROM portal_notificacoes WHERE papel = 'admin' "
        "OR (producao_id IS NULL AND proposta_id IS NULL)"
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("portal_notificacoes", recreate="always",
                                  copy_from=_sqlite_table(extended=True)) as batch:
            batch.drop_constraint("ck_portal_notificacao_papel", type_="check")
            batch.drop_constraint("ck_portal_notificacao_contexto", type_="check")
            for name, _ in NEW_COLUMNS:
                batch.drop_column(name)
            batch.create_check_constraint("ck_portal_notificacao_papel", OLD_ROLES)
            batch.create_check_constraint("ck_portal_notificacao_contexto", OLD_CONTEXT)
        return
    op.execute("ALTER TABLE portal_notificacoes DROP CONSTRAINT ck_portal_notificacao_contexto")
    op.execute(f"ALTER TABLE portal_notificacoes ADD CONSTRAINT ck_portal_notificacao_contexto CHECK ({OLD_CONTEXT})")
    op.execute("ALTER TABLE portal_notificacoes DROP CONSTRAINT ck_portal_notificacao_papel")
    op.execute(f"ALTER TABLE portal_notificacoes ADD CONSTRAINT ck_portal_notificacao_papel CHECK ({OLD_ROLES})")
    for name, _ in NEW_COLUMNS:
        op.drop_index(f"ix_portal_notificacao_{name}", table_name="portal_notificacoes")
        op.drop_column("portal_notificacoes", name)
