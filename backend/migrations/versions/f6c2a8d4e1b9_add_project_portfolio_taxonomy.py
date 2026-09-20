"""Add public portfolio taxonomy to projects.

Revision ID: f6c2a8d4e1b9
Revises: e2f7c1a9b4d8
"""

from alembic import op
import sqlalchemy as sa


revision: str = "f6c2a8d4e1b9"
down_revision: str = "e2f7c1a9b4d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projetos") as batch_op:
        batch_op.add_column(sa.Column("vertical", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("segmentos_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("case_type", sa.String(length=32), nullable=True))
        batch_op.create_check_constraint(
            "ck_projetos_vertical_valida",
            "vertical IS NULL OR vertical IN ('artists', 'creators', 'media_games')",
        )
        batch_op.create_check_constraint(
            "ck_projetos_case_type_valido",
            "case_type IS NULL OR case_type IN ('client_case', 'demo', 'concept_project', 'study')",
        )
        batch_op.create_index("ix_projetos_vertical", ["vertical"])
        batch_op.create_index("ix_projetos_case_type", ["case_type"])

    op.execute("UPDATE projetos SET segmentos_json = '[]' WHERE segmentos_json IS NULL")

    with op.batch_alter_table("projetos") as batch_op:
        batch_op.alter_column(
            "segmentos_json",
            existing_type=sa.JSON(),
            nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("projetos") as batch_op:
        batch_op.drop_index("ix_projetos_case_type")
        batch_op.drop_index("ix_projetos_vertical")
        batch_op.drop_constraint("ck_projetos_case_type_valido", type_="check")
        batch_op.drop_constraint("ck_projetos_vertical_valida", type_="check")
        batch_op.drop_column("case_type")
        batch_op.drop_column("segmentos_json")
        batch_op.drop_column("vertical")
