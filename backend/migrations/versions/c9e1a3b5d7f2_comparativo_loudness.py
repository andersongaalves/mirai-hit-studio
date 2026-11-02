"""Before/after comparison chosen by the Admin and the integrated loudness of audio files.

Revision ID: c9e1a3b5d7f2
Revises: b2d4f6a8c0e1
"""
import sqlalchemy as sa
from alembic import op

revision = "c9e1a3b5d7f2"
down_revision = "b2d4f6a8c0e1"
branch_labels = None
depends_on = None

FKS = (
    ("comparativo_antes_arquivo_id", "fk_producoes_comparativo_antes"),
    ("comparativo_depois_arquivo_id", "fk_producoes_comparativo_depois"),
)


def upgrade():
    op.add_column("producao_arquivos", sa.Column("lufs_integrado", sa.Float(), nullable=True))
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producoes") as batch:
            for column, name in FKS:
                batch.add_column(sa.Column(column, sa.Integer(), nullable=True))
                batch.create_foreign_key(name, "producao_arquivos", [column], ["id"], ondelete="SET NULL")
    else:
        for column, name in FKS:
            op.add_column("producoes", sa.Column(column, sa.Integer(), nullable=True))
            op.create_foreign_key(name, "producoes", "producao_arquivos", [column], ["id"], ondelete="SET NULL")


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producoes") as batch:
            for column, name in FKS:
                batch.drop_constraint(name, type_="foreignkey")
                batch.drop_column(column)
        with op.batch_alter_table("producao_arquivos") as batch:
            batch.drop_column("lufs_integrado")
    else:
        for column, name in FKS:
            op.drop_constraint(name, "producoes", type_="foreignkey")
            op.drop_column("producoes", column)
        op.drop_column("producao_arquivos", "lufs_integrado")
