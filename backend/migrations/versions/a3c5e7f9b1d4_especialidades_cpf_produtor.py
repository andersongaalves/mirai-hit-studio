"""Producer specialties and the beatmaker CPF used in beat contracts.

Revision ID: a3c5e7f9b1d4
Revises: f2b4d6e8a0c3
"""
import sqlalchemy as sa
from alembic import op

revision = "a3c5e7f9b1d4"
down_revision = "f2b4d6e8a0c3"
branch_labels = None
depends_on = None


def upgrade():
    # Plain ADD COLUMN: no table rebuild on SQLite. Rules live in the application.
    op.add_column("usuarios", sa.Column("especialidades", sa.String(100), nullable=True))
    op.add_column("usuarios", sa.Column("cpf", sa.String(11), nullable=True))
    # Producers who already sell beats are beatmakers; their CPF is filled in by the Admin.
    op.execute(
        "UPDATE usuarios SET especialidades = 'beatmaker' "
        "WHERE role = 'produtor' AND painel_beats = TRUE"
    )


def downgrade():
    op.execute("ALTER TABLE usuarios DROP COLUMN cpf")
    op.execute("ALTER TABLE usuarios DROP COLUMN especialidades")
