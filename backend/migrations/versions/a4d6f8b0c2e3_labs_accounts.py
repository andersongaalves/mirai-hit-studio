"""Mirai Hit Labs accounts: customers who buy plugins without a studio portal account.

- usuarios.somente_labs: the account was created on the Labs store; it buys, downloads and
  sees its plugins there, but has no access to the studio client portal.
- cliente_acessos.canal / idioma: where the sign-up came from (studio or Labs) and its
  language, so confirmation and password e-mails send people back to the right site.
- cliente_acessos.somente_labs: the account being created is Labs-only (a new customer
  who signed up on the store, not a studio client joining its existing record).

Revision ID: a4d6f8b0c2e3
Revises: f2c4e6a8b0d1
"""
import sqlalchemy as sa
from alembic import op

revision = "a4d6f8b0c2e3"
down_revision = "f2c4e6a8b0d1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("usuarios", sa.Column("somente_labs", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("cliente_acessos", sa.Column("canal", sa.String(8), nullable=False, server_default="studio"))
    op.add_column("cliente_acessos", sa.Column("idioma", sa.String(5), nullable=False, server_default="pt"))
    op.add_column("cliente_acessos", sa.Column("somente_labs", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("cliente_acessos") as batch:
        batch.create_check_constraint("ck_cliente_acessos_canal_valido", "canal IN ('studio', 'labs')")
        batch.create_check_constraint("ck_cliente_acessos_idioma_valido", "idioma IN ('pt', 'en')")
        batch.create_check_constraint("ck_cliente_acessos_somente_labs_canal", "NOT somente_labs OR canal = 'labs'")


def downgrade():
    with op.batch_alter_table("cliente_acessos") as batch:
        batch.drop_constraint("ck_cliente_acessos_somente_labs_canal", type_="check")
        batch.drop_constraint("ck_cliente_acessos_idioma_valido", type_="check")
        batch.drop_constraint("ck_cliente_acessos_canal_valido", type_="check")
    op.drop_column("cliente_acessos", "somente_labs")
    op.drop_column("cliente_acessos", "idioma")
    op.drop_column("cliente_acessos", "canal")
    op.drop_column("usuarios", "somente_labs")
