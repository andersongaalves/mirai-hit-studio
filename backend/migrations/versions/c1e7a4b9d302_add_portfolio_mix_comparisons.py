"""add portfolio mix comparisons

Revision ID: c1e7a4b9d302
Revises: a7d4e9c2b610
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c1e7a4b9d302"
down_revision: str | Sequence[str] | None = "a7d4e9c2b610"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("projetos") as batch_op:
        batch_op.add_column(sa.Column("audio_before_key", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("audio_after_key", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column(
                "show_mix_comparison_on_landing",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(sa.Column("landing_order", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_projetos_mix_comparison_destaque_valido",
            "NOT show_mix_comparison_on_landing OR "
            "(audio_before_key IS NOT NULL AND audio_after_key IS NOT NULL "
            "AND landing_order BETWEEN 1 AND 4)",
        )
        batch_op.create_check_constraint(
            "ck_projetos_mix_comparison_order_valida",
            "show_mix_comparison_on_landing OR landing_order IS NULL",
        )

    op.create_index(
        "uq_projetos_mix_comparison_landing_order",
        "projetos",
        ["landing_order"],
        unique=True,
        postgresql_where=sa.text("show_mix_comparison_on_landing"),
    )


def downgrade() -> None:
    op.drop_index("uq_projetos_mix_comparison_landing_order", table_name="projetos")
    with op.batch_alter_table("projetos") as batch_op:
        batch_op.drop_constraint("ck_projetos_mix_comparison_order_valida", type_="check")
        batch_op.drop_constraint("ck_projetos_mix_comparison_destaque_valido", type_="check")
        batch_op.drop_column("landing_order")
        batch_op.drop_column("show_mix_comparison_on_landing")
        batch_op.drop_column("audio_after_key")
        batch_op.drop_column("audio_before_key")
