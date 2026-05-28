"""add v2 normalized tables

Revision ID: 20260528_0002
Revises: 20260528_0001
Create Date: 2026-05-28 00:00:01.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0002"
down_revision = "20260528_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_inventory_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_dataset_id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=120), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=False),
        sa.Column("fulfillment_channel", sa.String(length=80), nullable=True),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("listing_status", sa.String(length=80), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("is_active_listing", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["marketplace_id"],
            ["marketplaces.id"],
            name=op.f("fk_normalized_inventory_daily_marketplace_id_marketplaces"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_dataset_id"],
            ["raw_datasets.id"],
            name=op.f("fk_normalized_inventory_daily_raw_dataset_id_raw_datasets"),
        ),
        sa.ForeignKeyConstraint(
            ["seller_account_id"],
            ["seller_accounts.id"],
            name=op.f("fk_normalized_inventory_daily_seller_account_id_seller_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_normalized_inventory_daily")),
    )
    op.create_table(
        "normalized_ads_search_term_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_dataset_id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("campaign_name", sa.String(length=255), nullable=False),
        sa.Column("search_term", sa.String(length=500), nullable=False),
        sa.Column("impressions", sa.Integer(), nullable=False),
        sa.Column("clicks", sa.Integer(), nullable=False),
        sa.Column("spend", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("attributed_sales", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("attributed_orders", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["marketplace_id"],
            ["marketplaces.id"],
            name=op.f("fk_normalized_ads_search_term_daily_marketplace_id_marketplaces"),
        ),
        sa.ForeignKeyConstraint(
            ["raw_dataset_id"],
            ["raw_datasets.id"],
            name=op.f("fk_normalized_ads_search_term_daily_raw_dataset_id_raw_datasets"),
        ),
        sa.ForeignKeyConstraint(
            ["seller_account_id"],
            ["seller_accounts.id"],
            name=op.f("fk_normalized_ads_search_term_daily_seller_account_id_seller_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_normalized_ads_search_term_daily")),
    )


def downgrade() -> None:
    op.drop_table("normalized_ads_search_term_daily")
    op.drop_table("normalized_inventory_daily")
