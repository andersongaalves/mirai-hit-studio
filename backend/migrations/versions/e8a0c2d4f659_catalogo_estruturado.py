"""Catalog rework: max minutes per audio track and combos sold like services.

Revision ID: e8a0c2d4f659
Revises: d6f8b0c2e437
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e8a0c2d4f659"
down_revision = "d6f8b0c2e437"
branch_labels = None
depends_on = None

DURACAO = "max_duracao_min IS NULL OR max_duracao_min BETWEEN 1 AND 60"


def upgrade():
    # Additive only; existing services keep their content (readers convert it on the fly).
    for tabela in ("servico_cotas_arquivo", "producao_cotas_arquivo"):
        op.add_column(tabela, sa.Column("max_duracao_min", sa.Integer(), nullable=True))
        op.create_check_constraint(f"ck_{tabela}_duracao", tabela, DURACAO)
    op.add_column("combos", sa.Column("subtitulo", sa.String(length=150), nullable=False, server_default=""))
    op.add_column("combos", sa.Column("aplica_desconto", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("combos", sa.Column(
        "destaques", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False,
        server_default=sa.text("'[]'"),
    ))
    with op.batch_alter_table("combos") as batch:
        batch.alter_column("descricao", existing_type=sa.String(length=300), type_=sa.String(length=1000),
                           existing_nullable=False)


def downgrade():
    with op.batch_alter_table("combos") as batch:
        batch.alter_column("descricao", existing_type=sa.String(length=1000), type_=sa.String(length=300),
                           existing_nullable=False)
        batch.drop_column("destaques")
        batch.drop_column("aplica_desconto")
        batch.drop_column("subtitulo")
    for tabela in ("producao_cotas_arquivo", "servico_cotas_arquivo"):
        with op.batch_alter_table(tabela) as batch:
            batch.drop_constraint(f"ck_{tabela}_duracao", type_="check")
            batch.drop_column("max_duracao_min")
