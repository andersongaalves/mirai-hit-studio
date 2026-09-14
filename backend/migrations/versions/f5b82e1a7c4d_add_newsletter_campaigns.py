"""Add newsletter consent, campaigns and deliveries.

Revision ID: f5b82e1a7c4d
Revises: c8f4e2d91a7b
"""

import secrets

from alembic import op
import sqlalchemy as sa


revision: str = "f5b82e1a7c4d"
down_revision: str = "c8f4e2d91a7b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("newsletter") as batch_op:
        batch_op.add_column(sa.Column("nome", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("unsubscribe_token", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True))

    bind = op.get_bind()
    bind.execute(sa.text("UPDATE newsletter SET consent_at = data_cadastro WHERE consent_at IS NULL"))
    for row in bind.execute(sa.text("SELECT id FROM newsletter WHERE unsubscribe_token IS NULL")):
        bind.execute(
            sa.text("UPDATE newsletter SET unsubscribe_token = :token WHERE id = :id"),
            {"id": row.id, "token": secrets.token_urlsafe(32)},
        )

    with op.batch_alter_table("newsletter") as batch_op:
        batch_op.alter_column("consent_at", existing_type=sa.DateTime(timezone=True), nullable=False)
        batch_op.alter_column("unsubscribe_token", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_newsletter_unsubscribe_token", ["unsubscribe_token"])

    op.create_table(
        "newsletter_campaigns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo_interno", sa.String(length=120), nullable=False),
        sa.Column("assunto", sa.String(length=160), nullable=False),
        sa.Column("preview_text", sa.String(length=200), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_newsletter_campaigns_id", "newsletter_campaigns", ["id"])
    op.create_index("ix_newsletter_campaigns_status", "newsletter_campaigns", ["status"])
    op.create_index("ix_newsletter_campaigns_created_by_id", "newsletter_campaigns", ["created_by_id"])
    op.create_table(
        "newsletter_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=False),
        sa.Column("subscriber_id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(length=150), nullable=False),
        sa.Column("provider_message_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["campaign_id"], ["newsletter_campaigns.id"]),
        sa.ForeignKeyConstraint(["subscriber_id"], ["newsletter.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id", "subscriber_id", name="uq_newsletter_delivery_campaign_subscriber"),
    )
    op.create_index("ix_newsletter_deliveries_id", "newsletter_deliveries", ["id"])
    op.create_index("ix_newsletter_deliveries_campaign_id", "newsletter_deliveries", ["campaign_id"])
    op.create_index("ix_newsletter_deliveries_subscriber_id", "newsletter_deliveries", ["subscriber_id"])
    op.create_index("ix_newsletter_deliveries_status", "newsletter_deliveries", ["status"])


def downgrade() -> None:
    op.drop_index("ix_newsletter_deliveries_id", table_name="newsletter_deliveries")
    op.drop_index("ix_newsletter_deliveries_status", table_name="newsletter_deliveries")
    op.drop_index("ix_newsletter_deliveries_subscriber_id", table_name="newsletter_deliveries")
    op.drop_index("ix_newsletter_deliveries_campaign_id", table_name="newsletter_deliveries")
    op.drop_table("newsletter_deliveries")
    op.drop_index("ix_newsletter_campaigns_id", table_name="newsletter_campaigns")
    op.drop_index("ix_newsletter_campaigns_created_by_id", table_name="newsletter_campaigns")
    op.drop_index("ix_newsletter_campaigns_status", table_name="newsletter_campaigns")
    op.drop_table("newsletter_campaigns")
    with op.batch_alter_table("newsletter") as batch_op:
        batch_op.drop_constraint("uq_newsletter_unsubscribe_token", type_="unique")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("unsubscribe_token")
        batch_op.drop_column("unsubscribed_at")
        batch_op.drop_column("consent_at")
        batch_op.drop_column("nome")
