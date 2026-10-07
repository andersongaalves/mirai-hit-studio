"""Add the authoritative proposal payment policy.

Revision ID: c5f2a7d9e184
Revises: b3e6f9a2c741
"""

import json
import logging

import sqlalchemy as sa
from alembic import op

revision = "c5f2a7d9e184"
down_revision = "b3e6f9a2c741"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")
DEFAULT_POLICY = "entrada_50_50"


def _payment_entries(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return []
    return value if isinstance(value, list) else []


def _manual_link_counts(bind):
    rows = bind.execute(sa.text("SELECT pagamentos_json FROM propostas")).scalars()
    with_urls = contradictions = 0
    for raw in rows:
        entries = [item for item in _payment_entries(raw) if isinstance(item, dict)]
        linked_types = {
            str(item.get("tipo") or "")
            for item in entries
            if isinstance(item.get("url"), str) and item["url"].strip()
        }
        if linked_types:
            with_urls += 1
        if "integral" in linked_types and not linked_types.intersection(
            {"parcial_1", "parcial_2"}
        ):
            contradictions += 1
    return with_urls, contradictions


def _preflight(bind):
    scalar = lambda statement: int(bind.execute(sa.text(statement)).scalar_one())
    with_urls, contradictions = _manual_link_counts(bind)
    counts = {
        "total": scalar("SELECT count(*) FROM propostas"),
        "sent": scalar("SELECT count(*) FROM propostas WHERE status = 'enviada'"),
        "accepted": scalar("SELECT count(*) FROM propostas WHERE status = 'aceita'"),
        "with_production": scalar(
            """SELECT count(*) FROM propostas p
               WHERE EXISTS (
                   SELECT 1 FROM producoes pr WHERE pr.orcamento_id = p.orcamento_id
               )"""
        ),
        "with_charge": scalar(
            """SELECT count(*) FROM propostas p
               WHERE EXISTS (
                   SELECT 1 FROM cobrancas c WHERE c.proposta_id = p.id
               )"""
        ),
        "with_approved_payment": scalar(
            """SELECT count(*) FROM propostas p
               WHERE EXISTS (
                   SELECT 1 FROM cobrancas c
                   JOIN pagamentos pg ON pg.cobranca_id = c.id
                   WHERE c.proposta_id = p.id AND pg.status = 'aprovado'
               )"""
        ),
        "with_manual_urls": with_urls,
        "possible_link_contradictions": contradictions,
    }
    logger.info(
        "proposal_payment_policy_preflight "
        "total=%(total)d sent=%(sent)d accepted=%(accepted)d "
        "with_production=%(with_production)d with_charge=%(with_charge)d "
        "with_approved_payment=%(with_approved_payment)d "
        "with_manual_urls=%(with_manual_urls)d "
        "possible_link_contradictions=%(possible_link_contradictions)d",
        counts,
    )
    return counts


def upgrade():
    op.add_column(
        "propostas",
        sa.Column("politica_pagamento", sa.String(20), nullable=True),
    )
    bind = op.get_bind()
    _preflight(bind)
    bind.execute(
        sa.text(
            "UPDATE propostas SET politica_pagamento = :policy "
            "WHERE politica_pagamento IS NULL"
        ),
        {"policy": DEFAULT_POLICY},
    )
    with op.batch_alter_table("propostas") as batch_op:
        batch_op.create_check_constraint(
            "ck_propostas_politica_pagamento_valida",
            "politica_pagamento IN ('integral', 'entrada_50_50')",
        )
        batch_op.alter_column(
            "politica_pagamento",
            existing_type=sa.String(20),
            nullable=False,
            server_default=sa.text("'entrada_50_50'"),
        )


def downgrade():
    with op.batch_alter_table("propostas") as batch_op:
        batch_op.drop_constraint(
            "ck_propostas_politica_pagamento_valida",
            type_="check",
        )
        batch_op.drop_column("politica_pagamento")
