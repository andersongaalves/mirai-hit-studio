"""Beat license reservations expire and cancelled licenses record why (AUD6-S06-001/002)."""

import sqlalchemy as sa
from alembic import op

revision = "a4c6e8f0b217"
down_revision = "f3c5d7e9a102"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("beat_licencas") as batch:
        batch.add_column(sa.Column("expira_em", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("cancelada_em", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("motivo_cancelamento", sa.String(24), nullable=True))
        batch.create_check_constraint(
            "ck_beat_licencas_motivo_cancelamento",
            "motivo_cancelamento IS NULL OR motivo_cancelamento IN "
            "('expirada','admin','pagamento_revertido')",
        )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "UPDATE beat_licencas SET expira_em = created_at + interval '48 hours' "
            "WHERE status = 'reservada' AND expira_em IS NULL"
        )


def downgrade():
    with op.batch_alter_table("beat_licencas") as batch:
        batch.drop_constraint("ck_beat_licencas_motivo_cancelamento", type_="check")
        batch.drop_column("motivo_cancelamento")
        batch.drop_column("cancelada_em")
        batch.drop_column("expira_em")
