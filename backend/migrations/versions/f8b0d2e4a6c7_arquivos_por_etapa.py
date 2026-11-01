"""Production files belong to a contract stage (nullable: general files).

Revision ID: f8b0d2e4a6c7
Revises: d6f8a0b2c415
"""
import sqlalchemy as sa
from alembic import op

revision = "f8b0d2e4a6c7"
down_revision = "d6f8a0b2c415"
branch_labels = None
depends_on = None

INDEX = "ix_producao_arquivos_etapa_id"
FK = "fk_producao_arquivos_etapa_id"


def upgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producao_arquivos") as batch:
            batch.add_column(sa.Column("etapa_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(FK, "producao_etapas", ["etapa_id"], ["id"], ondelete="SET NULL")
            batch.create_index(INDEX, ["etapa_id"])
    else:
        op.add_column("producao_arquivos", sa.Column("etapa_id", sa.Integer(), nullable=True))
        op.create_foreign_key(FK, "producao_arquivos", "producao_etapas", ["etapa_id"], ["id"], ondelete="SET NULL")
        op.create_index(INDEX, "producao_arquivos", ["etapa_id"])


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producao_arquivos") as batch:
            batch.drop_index(INDEX)
            batch.drop_constraint(FK, type_="foreignkey")
            batch.drop_column("etapa_id")
    else:
        op.drop_index(INDEX, table_name="producao_arquivos")
        op.drop_constraint(FK, "producao_arquivos", type_="foreignkey")
        op.drop_column("producao_arquivos", "etapa_id")
