"""Configurable automatic audio tag leveling controls.

Revision ID: b4d6f8a0c2e5
Revises: a3c5e7f9b1d4
"""

import sqlalchemy as sa
from alembic import op

revision = "b4d6f8a0c2e5"
down_revision = "a3c5e7f9b1d4"
branch_labels = None
depends_on = None

TABLES = ("audio_tag_perfis", "previa_tag_jobs")


def _columns(batch):
    batch.add_column(sa.Column("nivelamento_automatico", sa.Boolean(), nullable=False, server_default=sa.true()))
    batch.add_column(sa.Column("alvo_relativo_db", sa.Float(), nullable=False, server_default="-3"))
    batch.add_column(sa.Column("ganho_min_db", sa.Float(), nullable=False, server_default="-40"))
    batch.add_column(sa.Column("ganho_max_db", sa.Float(), nullable=False, server_default="30"))
    batch.add_column(sa.Column("silencio_lufs", sa.Float(), nullable=False, server_default="-60"))
    batch.add_column(sa.Column("limiter_dbfs", sa.Float(), nullable=False, server_default="-0.9"))


def _checks(batch, prefix):
    batch.create_check_constraint(f"ck_{prefix}_alvo_relativo", "alvo_relativo_db BETWEEN -30 AND 12")
    batch.create_check_constraint(f"ck_{prefix}_ganho_min", "ganho_min_db BETWEEN -60 AND 0")
    batch.create_check_constraint(f"ck_{prefix}_ganho_max", "ganho_max_db BETWEEN 0 AND 30")
    batch.create_check_constraint(f"ck_{prefix}_faixa_ganho", "ganho_min_db < ganho_max_db")
    batch.create_check_constraint(f"ck_{prefix}_silencio", "silencio_lufs BETWEEN -90 AND -20")
    batch.create_check_constraint(f"ck_{prefix}_limiter", "limiter_dbfs BETWEEN -12 AND -0.1")


def upgrade():
    for table, prefix in (("audio_tag_perfis", "audio_tag"), ("previa_tag_jobs", "previa_tag")):
        with op.batch_alter_table(table) as batch:
            _columns(batch)
            _checks(batch, prefix)


def downgrade():
    for table, prefix in (("previa_tag_jobs", "previa_tag"), ("audio_tag_perfis", "audio_tag")):
        with op.batch_alter_table(table) as batch:
            for suffix in ("limiter", "silencio", "faixa_ganho", "ganho_max", "ganho_min", "alvo_relativo"):
                batch.drop_constraint(f"ck_{prefix}_{suffix}", type_="check")
            for column in (
                "limiter_dbfs",
                "silencio_lufs",
                "ganho_max_db",
                "ganho_min_db",
                "alvo_relativo_db",
                "nivelamento_automatico",
            ):
                batch.drop_column(column)
