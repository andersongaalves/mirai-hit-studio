"""Separate beat formats, prices and private assets for admin review."""

import sqlalchemy as sa
from alembic import op

revision = "e2b4c6d8f901"
down_revision = "d7a2c4e6f810"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("beats") as batch:
        batch.add_column(sa.Column("preco_wav", sa.Numeric(12, 2)))
        batch.add_column(sa.Column("preco_multitrack", sa.Numeric(12, 2)))
        batch.add_column(sa.Column("mp3_ref", sa.String(180)))
        batch.add_column(sa.Column("wav_ref", sa.String(180)))
        batch.add_column(sa.Column("wav_sha256", sa.String(64)))
        batch.add_column(sa.Column("multitrack_ref", sa.String(180)))
        batch.add_column(sa.Column("multitrack_sha256", sa.String(64)))
        batch.add_column(sa.Column("multitrack_mime", sa.String(100)))
        batch.add_column(sa.Column("capa_ref", sa.String(180)))
        batch.add_column(sa.Column("capa_url", sa.String(1000)))
        batch.add_column(sa.Column("capa_sha256", sa.String(64)))
        batch.drop_constraint("ck_beats_algum_preco", type_="check")
        batch.create_check_constraint(
            "ck_beats_algum_preco",
            "preco_lease IS NOT NULL OR preco_wav IS NOT NULL OR preco_multitrack IS NOT NULL OR preco_exclusivo IS NOT NULL",
        )
        batch.create_check_constraint("ck_beats_preco_wav", "preco_wav IS NULL OR preco_wav > 0")
        batch.create_check_constraint("ck_beats_preco_multitrack", "preco_multitrack IS NULL OR preco_multitrack > 0")
        batch.create_unique_constraint("uq_beats_mp3_ref", ["mp3_ref"])
        batch.create_unique_constraint("uq_beats_wav_ref", ["wav_ref"])
        batch.create_unique_constraint("uq_beats_multitrack_ref", ["multitrack_ref"])
        batch.create_unique_constraint("uq_beats_capa_ref", ["capa_ref"])
    with op.batch_alter_table("orcamentos") as batch:
        batch.drop_constraint("ck_orcamentos_beat_licenca", type_="check")
        batch.create_check_constraint(
            "ck_orcamentos_beat_licenca",
            "(beat_id IS NULL AND licenca_beat IS NULL) OR (beat_id IS NOT NULL AND licenca_beat IN ('lease','lease_mp3','lease_wav','multitrack','exclusivo'))",
        )
    with op.batch_alter_table("beat_licencas") as batch:
        batch.drop_constraint("ck_beat_licencas_tipo", type_="check")
        batch.create_check_constraint(
            "ck_beat_licencas_tipo",
            "tipo IN ('lease','lease_mp3','lease_wav','multitrack','exclusivo')",
        )


def downgrade():
    with op.batch_alter_table("beat_licencas") as batch:
        batch.drop_constraint("ck_beat_licencas_tipo", type_="check")
        batch.create_check_constraint("ck_beat_licencas_tipo", "tipo IN ('lease','exclusivo')")
    with op.batch_alter_table("orcamentos") as batch:
        batch.drop_constraint("ck_orcamentos_beat_licenca", type_="check")
        batch.create_check_constraint(
            "ck_orcamentos_beat_licenca",
            "(beat_id IS NULL AND licenca_beat IS NULL) OR (beat_id IS NOT NULL AND licenca_beat IN ('lease','exclusivo'))",
        )
    with op.batch_alter_table("beats") as batch:
        batch.drop_constraint("uq_beats_mp3_ref", type_="unique")
        batch.drop_constraint("uq_beats_wav_ref", type_="unique")
        batch.drop_constraint("uq_beats_multitrack_ref", type_="unique")
        batch.drop_constraint("uq_beats_capa_ref", type_="unique")
        batch.drop_constraint("ck_beats_preco_wav", type_="check")
        batch.drop_constraint("ck_beats_preco_multitrack", type_="check")
        batch.drop_constraint("ck_beats_algum_preco", type_="check")
        batch.create_check_constraint("ck_beats_algum_preco", "preco_lease IS NOT NULL OR preco_exclusivo IS NOT NULL")
        for column in ("capa_sha256", "capa_url", "capa_ref", "multitrack_mime", "multitrack_sha256", "multitrack_ref", "wav_sha256", "wav_ref", "mp3_ref", "preco_multitrack", "preco_wav"):
            batch.drop_column(column)
