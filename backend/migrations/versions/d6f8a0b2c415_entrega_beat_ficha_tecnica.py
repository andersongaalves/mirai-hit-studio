"""Technical sheet for custom beat final deliveries.

Revision ID: d6f8a0b2c415
Revises: c5e7a9b1d304
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d6f8a0b2c415"
down_revision = "c5e7a9b1d304"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("producao_entregas_finais", sa.Column("bpm", sa.Integer()))
    op.add_column("producao_entregas_finais", sa.Column("tonalidade", sa.String(20)))
    op.add_column(
        "producao_entregas_finais",
        sa.Column(
            "creditos_adicionais",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producao_entregas_finais") as batch:
            batch.create_check_constraint(
                "ck_entregas_finais_bpm_valido",
                "bpm IS NULL OR bpm BETWEEN 20 AND 300",
            )
    else:
        op.create_check_constraint(
            "ck_entregas_finais_bpm_valido",
            "producao_entregas_finais",
            "bpm IS NULL OR bpm BETWEEN 20 AND 300",
        )


def downgrade():
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("producao_entregas_finais") as batch:
            batch.drop_constraint("ck_entregas_finais_bpm_valido", type_="check")
            batch.drop_column("creditos_adicionais")
            batch.drop_column("tonalidade")
            batch.drop_column("bpm")
    else:
        op.drop_constraint("ck_entregas_finais_bpm_valido", "producao_entregas_finais", type_="check")
        op.drop_column("producao_entregas_finais", "creditos_adicionais")
        op.drop_column("producao_entregas_finais", "tonalidade")
        op.drop_column("producao_entregas_finais", "bpm")
