"""Pause new quote requests from the Admin (busy schedule).

Revision ID: c9e1a3b5d7f8
Revises: b8d0f2a4c6e7
"""
import sqlalchemy as sa
from alembic import op

revision = "c9e1a3b5d7f8"
down_revision = "b8d0f2a4c6e7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("configuracoes", sa.Column("orcamentos_pausados", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("configuracoes", sa.Column("orcamentos_pausa_mensagem", sa.String(500), nullable=True))
    op.add_column("configuracoes", sa.Column("orcamentos_pausados_em", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("configuracoes", "orcamentos_pausados_em")
    op.drop_column("configuracoes", "orcamentos_pausa_mensagem")
    op.drop_column("configuracoes", "orcamentos_pausados")
