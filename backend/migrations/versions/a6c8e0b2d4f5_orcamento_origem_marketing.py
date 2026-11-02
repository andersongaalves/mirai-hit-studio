"""Where each lead came from (campaign, referring site, landing page) for the Marketing area.

Revision ID: a6c8e0b2d4f5
Revises: f4b6d8a0c2e3
"""
import sqlalchemy as sa
from alembic import op

revision = "a6c8e0b2d4f5"
down_revision = "f4b6d8a0c2e3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orcamentos", sa.Column("origem_marketing", sa.JSON(), nullable=True))


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("orcamentos") as batch:
            batch.drop_column("origem_marketing")
    else:
        op.drop_column("orcamentos", "origem_marketing")
