"""Add administrator-configurable beat upload limits."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3c5d7e9a102"
down_revision = "e2b4c6d8f901"
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade():
    op.add_column(
        "configuracoes",
        sa.Column(
            "beat_upload_limits_json",
            _json_type(),
            nullable=False,
            server_default=sa.text(
                "'{\"capa_mb\":10,\"mp3_mb\":50,\"wav_mb\":50,\"multitrack_mb\":50,\"multitrack_mode\":\"arquivo\"}'"
            ),
        ),
    )
    with op.batch_alter_table("beats") as batch:
        batch.add_column(sa.Column("multitrack_url", sa.String(2000)))
        batch.create_check_constraint(
            "ck_beats_multitrack_origem_unica",
            "multitrack_ref IS NULL OR multitrack_url IS NULL",
        )


def downgrade():
    with op.batch_alter_table("beats") as batch:
        batch.drop_constraint("ck_beats_multitrack_origem_unica", type_="check")
        batch.drop_column("multitrack_url")
    op.drop_column("configuracoes", "beat_upload_limits_json")
