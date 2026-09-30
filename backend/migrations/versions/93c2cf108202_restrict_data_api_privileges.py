"""restrict data api privileges

Revision ID: 93c2cf108202
Revises: b8c41e7d290a
Create Date: 2026-09-30 09:41:30.758158

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '93c2cf108202'
down_revision: Union[str, Sequence[str], None] = 'b8c41e7d290a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


LEGACY_DATA_API_TABLES = (
    "alembic_version",
    "audit_logs",
    "clientes",
    "cobrancas",
    "configuracoes",
    "newsletter",
    "newsletter_campaigns",
    "newsletter_deliveries",
    "orcamentos",
    "pagamentos",
    "producoes",
    "projetos",
    "propostas",
    "provider_webhook_events",
    "servicos",
    "usuarios",
)

LEGACY_DATA_API_SEQUENCES = (
    "audit_logs_id_seq",
    "clientes_id_seq",
    "cobrancas_id_seq",
    "configuracoes_id_seq",
    "newsletter_id_seq",
    "newsletter_campaigns_id_seq",
    "newsletter_deliveries_id_seq",
    "orcamentos_id_seq",
    "pagamentos_id_seq",
    "producoes_id_seq",
    "projetos_id_seq",
    "propostas_id_seq",
    "provider_webhook_events_id_seq",
    "servicos_id_seq",
    "usuarios_id_seq",
)


def _public_objects(names: tuple[str, ...]) -> str:
    return ", ".join(f'public."{name}"' for name in names)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM anon, authenticated")
    op.execute("REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated")
    op.execute("REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon, authenticated")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON TABLES FROM anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE ALL PRIVILEGES ON SEQUENCES FROM anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon, authenticated"
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        f"GRANT ALL PRIVILEGES ON TABLE {_public_objects(LEGACY_DATA_API_TABLES)} "
        "TO anon, authenticated"
    )
    op.execute(
        f"GRANT ALL PRIVILEGES ON SEQUENCE {_public_objects(LEGACY_DATA_API_SEQUENCES)} "
        "TO anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT ALL PRIVILEGES ON TABLES TO anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT ALL PRIVILEGES ON SEQUENCES TO anon, authenticated"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public "
        "GRANT EXECUTE ON FUNCTIONS TO PUBLIC, anon, authenticated"
    )
