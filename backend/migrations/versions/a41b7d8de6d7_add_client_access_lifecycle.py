"""add client access lifecycle

Revision ID: a41b7d8de6d7
Revises: 5b7c9d1e4f62
Create Date: 2026-10-04 14:44:38.022632

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a41b7d8de6d7"
down_revision = "5b7c9d1e4f62"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cliente_acessos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "cliente_id",
            sa.Integer(),
            sa.ForeignKey("clientes.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("email_normalizado", sa.String(254), nullable=False),
        sa.Column("origem", sa.String(24), nullable=False),
        sa.Column("token_finalidade", sa.String(24), nullable=True),
        sa.Column("token_hash", sa.String(64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("token_revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("privacy_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "activation_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "send_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("request_fingerprint_hash", sa.String(64), nullable=True),
        sa.Column(
            "invited_by_user_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
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
            "origem IN ('admin_invite', 'public_signup')",
            name="ck_cliente_acessos_origem_valida",
        ),
        sa.CheckConstraint(
            "token_finalidade IS NULL OR "
            "token_finalidade IN ('convite', 'verificacao', 'recuperacao')",
            name="ck_cliente_acessos_token_finalidade_valida",
        ),
        sa.CheckConstraint(
            "(token_hash IS NULL AND token_finalidade IS NULL "
            "AND token_expires_at IS NULL) OR "
            "(token_hash IS NOT NULL AND token_finalidade IS NOT NULL "
            "AND token_expires_at IS NOT NULL)",
            name="ck_cliente_acessos_token_completo",
        ),
        sa.CheckConstraint(
            "token_hash IS NULL OR length(token_hash) = 64",
            name="ck_cliente_acessos_token_hash_valido",
        ),
        sa.CheckConstraint(
            "request_fingerprint_hash IS NULL "
            "OR length(request_fingerprint_hash) = 64",
            name="ck_cliente_acessos_fingerprint_valido",
        ),
        sa.CheckConstraint(
            "token_consumed_at IS NULL OR token_revoked_at IS NULL",
            name="ck_cliente_acessos_token_estado_unico",
        ),
        sa.CheckConstraint(
            "activation_attempts >= 0 AND send_count >= 0",
            name="ck_cliente_acessos_contadores_validos",
        ),
        sa.CheckConstraint(
            "(origem = 'admin_invite' AND invited_by_user_id IS NOT NULL) OR "
            "(origem = 'public_signup' AND invited_by_user_id IS NULL)",
            name="ck_cliente_acessos_origem_convite_coerente",
        ),
        sa.CheckConstraint(
            "origem <> 'public_signup' OR privacy_accepted_at IS NOT NULL",
            name="ck_cliente_acessos_privacidade_cadastro",
        ),
        sa.UniqueConstraint("cliente_id", name="uq_cliente_acessos_cliente_id"),
        sa.UniqueConstraint("usuario_id", name="uq_cliente_acessos_usuario_id"),
        sa.UniqueConstraint(
            "email_normalizado",
            name="uq_cliente_acessos_email_normalizado",
        ),
        sa.UniqueConstraint("token_hash", name="uq_cliente_acessos_token_hash"),
    )
    op.create_index(
        "ix_cliente_acessos_token_expires_at",
        "cliente_acessos",
        ["token_expires_at"],
    )
    op.create_index(
        "ix_cliente_acessos_request_fingerprint_hash",
        "cliente_acessos",
        ["request_fingerprint_hash"],
    )
    op.create_index(
        "ix_cliente_acessos_invited_by_user_id",
        "cliente_acessos",
        ["invited_by_user_id"],
    )

    op.create_table(
        "auth_rate_limits",
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "request_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
            "action IN ('signup', 'confirmation', 'resend', 'activation', 'recovery')",
            name="ck_auth_rate_limits_action_valida",
        ),
        sa.CheckConstraint(
            "length(key_hash) = 64",
            name="ck_auth_rate_limits_key_hash_valido",
        ),
        sa.CheckConstraint(
            "request_count >= 0",
            name="ck_auth_rate_limits_request_count_valido",
        ),
        sa.CheckConstraint(
            "expires_at > window_started_at",
            name="ck_auth_rate_limits_expiracao_valida",
        ),
        sa.CheckConstraint(
            "blocked_until IS NULL OR blocked_until >= window_started_at",
            name="ck_auth_rate_limits_bloqueio_valido",
        ),
    )
    op.create_index(
        "ix_auth_rate_limits_expires_at",
        "auth_rate_limits",
        ["expires_at"],
    )

    if op.get_bind().dialect.name == "postgresql":
        for table in ("cliente_acessos", "auth_rate_limits"):
            op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
            for role in ("anon", "authenticated"):
                op.execute(
                    "DO $$ BEGIN IF EXISTS "
                    f"(SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                    f"THEN REVOKE ALL ON TABLE {table} FROM {role}; "
                    "END IF; END; $$"
                )
        for role in ("anon", "authenticated"):
            op.execute(
                "DO $$ BEGIN IF EXISTS "
                f"(SELECT 1 FROM pg_roles WHERE rolname = '{role}') "
                "THEN REVOKE ALL ON SEQUENCE cliente_acessos_id_seq "
                f"FROM {role}; END IF; END; $$"
            )


def downgrade():
    op.drop_table("auth_rate_limits")
    op.drop_table("cliente_acessos")
