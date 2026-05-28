"""v2 operations

Revision ID: 20260528_0001
Revises: 3d4526765c0a
Create Date: 2026-05-28 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0001"
down_revision = "3d4526765c0a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("import_jobs", sa.Column("original_filename", sa.String(length=500), nullable=True))
    op.add_column("import_jobs", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))

    with op.batch_alter_table("daily_reports") as batch_op:
        batch_op.add_column(sa.Column("seller_account_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("marketplace_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("scope_type", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("report_kind", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("report_start_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("report_end_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("markdown_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("llm_status", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("llm_error", sa.Text(), nullable=True))
        batch_op.alter_column("report_date", existing_type=sa.Date(), nullable=True)
        batch_op.create_foreign_key(
            "fk_daily_reports_seller_account_id_seller_accounts",
            "seller_accounts",
            ["seller_account_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_daily_reports_marketplace_id_marketplaces",
            "marketplaces",
            ["marketplace_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_reports") as batch_op:
        batch_op.drop_constraint(
            "fk_daily_reports_marketplace_id_marketplaces",
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            "fk_daily_reports_seller_account_id_seller_accounts",
            type_="foreignkey",
        )
        batch_op.alter_column("report_date", existing_type=sa.Date(), nullable=False)
        batch_op.drop_column("llm_error")
        batch_op.drop_column("llm_status")
        batch_op.drop_column("markdown_path")
        batch_op.drop_column("status")
        batch_op.drop_column("report_end_date")
        batch_op.drop_column("report_start_date")
        batch_op.drop_column("report_kind")
        batch_op.drop_column("scope_type")
        batch_op.drop_column("marketplace_id")
        batch_op.drop_column("seller_account_id")

    op.drop_column("import_jobs", "deleted_at")
    op.drop_column("import_jobs", "original_filename")
