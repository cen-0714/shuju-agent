"""drop amazon oauth sessions

Revision ID: 20260529_0004
Revises: 20260528_0003
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_expires_at"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_status"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_selling_partner_id"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_state"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_table("amazon_authorization_sessions")


def downgrade() -> None:
    op.create_table(
        "amazon_authorization_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=160), nullable=False),
        sa.Column("amazon_state", sa.String(length=500), nullable=False),
        sa.Column("amazon_callback_uri", sa.Text(), nullable=False),
        sa.Column("selling_partner_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_amazon_authorization_sessions")),
        sa.UniqueConstraint("state", name=op.f("uq_amazon_authorization_sessions_state")),
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_state"),
        "amazon_authorization_sessions",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_selling_partner_id"),
        "amazon_authorization_sessions",
        ["selling_partner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_status"),
        "amazon_authorization_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_expires_at"),
        "amazon_authorization_sessions",
        ["expires_at"],
        unique=False,
    )
