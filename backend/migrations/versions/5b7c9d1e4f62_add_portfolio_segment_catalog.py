"""Add configurable portfolio segment catalog.

Revision ID: 5b7c9d1e4f62
Revises: 24ef7f883a03
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5b7c9d1e4f62"
down_revision: str = "24ef7f883a03"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _segment_ids(connection) -> list[str]:
    identifiers = set()
    for value in connection.execute(
        sa.text("SELECT segmentos_json FROM projetos")
    ).scalars():
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                continue
        if isinstance(value, list):
            identifiers.update(item for item in value if isinstance(item, str))
    return sorted(identifiers)


def upgrade() -> None:
    op.add_column(
        "configuracoes",
        sa.Column(
            "portfolio_segments_json",
            _json_type(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    connection = op.get_bind()
    catalog = [
        {
            "id": segment_id,
            "label": segment_id.replace("_", " ").title(),
            "active": True,
            "order": order,
            "retired": False,
        }
        for order, segment_id in enumerate(_segment_ids(connection), start=1)
    ]
    table = sa.table(
        "configuracoes",
        sa.column("portfolio_segments_json", _json_type()),
    )
    connection.execute(sa.update(table).values(portfolio_segments_json=catalog))


def downgrade() -> None:
    op.drop_column("configuracoes", "portfolio_segments_json")
