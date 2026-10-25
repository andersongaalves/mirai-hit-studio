"""Persistent request limits share auth_rate_limits (AUD6-S12-003)."""

import sqlalchemy as sa
from alembic import op

revision = "b5d7f9a1c328"
down_revision = "a4c6e8f0b217"
branch_labels = None
depends_on = None

BASE_ACTIONS = "'signup', 'confirmation', 'resend', 'activation', 'recovery'"
NEW_ACTIONS = "'login', 'login_account', 'budget', 'newsletter', 'checkout_payment', 'checkout_resume'"
NAME = "ck_auth_rate_limits_action_valida"


def _sqlite_table(actions):
    # SQLite cannot alter a CHECK in place; batch mode rebuilds the table from this definition.
    return sa.Table(
        "auth_rate_limits",
        sa.MetaData(),
        sa.Column("key_hash", sa.String(64), primary_key=True),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(f"action IN ({actions})", name=NAME),
        sa.CheckConstraint("length(key_hash) = 64", name="ck_auth_rate_limits_key_hash_valido"),
        sa.CheckConstraint("request_count >= 0", name="ck_auth_rate_limits_request_count_valido"),
        sa.CheckConstraint("expires_at > window_started_at", name="ck_auth_rate_limits_expiracao_valida"),
        sa.CheckConstraint(
            "blocked_until IS NULL OR blocked_until >= window_started_at",
            name="ck_auth_rate_limits_bloqueio_valido",
        ),
        sa.Index("ix_auth_rate_limits_expires_at", "expires_at"),
    )


def _replace(actions):
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("auth_rate_limits", copy_from=_sqlite_table(actions), recreate="always"):
            pass
        return
    op.execute(f"ALTER TABLE auth_rate_limits DROP CONSTRAINT {NAME}")
    op.execute(f"ALTER TABLE auth_rate_limits ADD CONSTRAINT {NAME} CHECK (action IN ({actions}))")


def upgrade():
    _replace(f"{BASE_ACTIONS}, {NEW_ACTIONS}")


def downgrade():
    op.execute(f"DELETE FROM auth_rate_limits WHERE action IN ({NEW_ACTIONS})")
    _replace(BASE_ACTIONS)
