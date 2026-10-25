"""Recovery e-mail and reset token for studio accounts (AUD6-S02-004).

Revision ID: e1a3c5d7f9b2
Revises: d8f0b2c4e6a3
"""
import sqlalchemy as sa
from alembic import op

revision = "e1a3c5d7f9b2"
down_revision = "d8f0b2c4e6a3"
branch_labels = None
depends_on = None

CHECK = "email IS NULL OR role IN ('admin', 'produtor')"


def upgrade():
    # Plain ADD COLUMN keeps SQLite from rebuilding usuarios (which would drop the lower(username) index).
    op.add_column("usuarios", sa.Column("email", sa.String(150), nullable=True))
    op.add_column("usuarios", sa.Column("reset_token_hash", sa.String(64), nullable=True))
    op.add_column("usuarios", sa.Column("reset_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("uq_usuarios_reset_token_hash", "usuarios", ["reset_token_hash"], unique=True)
    op.execute("CREATE UNIQUE INDEX uq_usuarios_email_lower ON usuarios (lower(email))")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(f"ALTER TABLE usuarios ADD CONSTRAINT ck_usuarios_email_interno CHECK ({CHECK})")


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        op.execute("ALTER TABLE usuarios DROP CONSTRAINT ck_usuarios_email_interno")
    op.execute("DROP INDEX uq_usuarios_email_lower")
    op.drop_index("uq_usuarios_reset_token_hash", table_name="usuarios")
    # Plain DROP COLUMN (SQLite >= 3.35): a batch rebuild of usuarios fails while
    # other tables reference it and would lose the lower(username) index.
    for column in ("reset_expires_at", "reset_token_hash", "email"):
        op.execute(f"ALTER TABLE usuarios DROP COLUMN {column}")
