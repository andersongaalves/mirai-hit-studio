"""Logins are unique regardless of letter case (AUD6-S02-006).

Revision ID: d8f0b2c4e6a3
Revises: c6e8a0b2d4f1
"""
from alembic import op

revision = "d8f0b2c4e6a3"
down_revision = "c6e8a0b2d4f1"
branch_labels = None
depends_on = None


def upgrade():
    # Production had no case collisions when this was decided (25/10/2026); a collision makes this fail loudly.
    op.execute("CREATE UNIQUE INDEX uq_usuarios_username_lower ON usuarios (lower(username))")


def downgrade():
    op.execute("DROP INDEX uq_usuarios_username_lower")
