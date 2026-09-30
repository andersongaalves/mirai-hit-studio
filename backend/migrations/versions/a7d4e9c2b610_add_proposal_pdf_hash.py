"""add proposal pdf hash

Revision ID: a7d4e9c2b610
Revises: 93c2cf108202
Create Date: 2026-09-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7d4e9c2b610"
down_revision: Union[str, Sequence[str], None] = "93c2cf108202"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("propostas", sa.Column("pdf_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("propostas", "pdf_sha256")
