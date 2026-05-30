"""add normalized order daily

Revision ID: 20260530_0006
Revises: 20260529_0005
Create Date: 2026-05-30 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260530_0006"
down_revision = "20260529_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "normalized_order_daily",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("raw_dataset_id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("sku", sa.String(length=120), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=True),
        sa.Column("product_name", sa.String(length=500), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("units_ordered", sa.Integer(), nullable=False),
        sa.Column("ordered_product_sales", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("order_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["raw_dataset_id"], ["raw_datasets.id"]),
        sa.ForeignKeyConstraint(["seller_account_id"], ["seller_accounts.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplaces.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_normalized_order_daily_seller_account_id",
        "normalized_order_daily",
        ["seller_account_id"],
    )
    op.create_index(
        "ix_normalized_order_daily_marketplace_id",
        "normalized_order_daily",
        ["marketplace_id"],
    )
    op.create_index(
        "ix_normalized_order_daily_report_date",
        "normalized_order_daily",
        ["report_date"],
    )
    op.create_index("ix_normalized_order_daily_sku", "normalized_order_daily", ["sku"])


def downgrade() -> None:
    op.drop_index("ix_normalized_order_daily_sku", table_name="normalized_order_daily")
    op.drop_index("ix_normalized_order_daily_report_date", table_name="normalized_order_daily")
    op.drop_index("ix_normalized_order_daily_marketplace_id", table_name="normalized_order_daily")
    op.drop_index(
        "ix_normalized_order_daily_seller_account_id",
        table_name="normalized_order_daily",
    )
    op.drop_table("normalized_order_daily")
