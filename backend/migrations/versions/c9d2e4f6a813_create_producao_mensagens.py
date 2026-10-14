"""Create the immutable message thread per production (Roadmap 3.0, 5.03).

Revision ID: c9d2e4f6a813
Revises: b4e6f8a1c302
"""

import sqlalchemy as sa
from alembic import op

revision = "c9d2e4f6a813"
down_revision = "b4e6f8a1c302"
branch_labels = None
depends_on = None


def upgrade():
    # Additive only: a new table; no existing row is read or changed.
    op.create_table(
        "producao_mensagens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("producao_id", sa.Integer(), sa.ForeignKey("producoes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("autor_usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("autor_papel", sa.String(length=20), nullable=False),
        sa.Column("audiencia", sa.String(length=20), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "responde_a_id",
            sa.Integer(),
            sa.ForeignKey("producao_mensagens.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "arquivo_id",
            sa.Integer(),
            sa.ForeignKey("producao_arquivos.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("autor_papel IN ('cliente', 'produtor', 'admin')", name="ck_producao_mensagens_papel"),
        sa.CheckConstraint("audiencia IN ('todos', 'equipe')", name="ck_producao_mensagens_audiencia"),
        sa.CheckConstraint("length(texto) BETWEEN 1 AND 2000", name="ck_producao_mensagens_texto"),
        sa.CheckConstraint(
            "autor_papel <> 'cliente' OR audiencia = 'todos'",
            name="ck_producao_mensagens_cliente_todos",
        ),
    )
    op.create_index("ix_producao_mensagens_producao_id", "producao_mensagens", ["producao_id"])


def downgrade():
    op.drop_index("ix_producao_mensagens_producao_id", table_name="producao_mensagens")
    op.drop_table("producao_mensagens")
