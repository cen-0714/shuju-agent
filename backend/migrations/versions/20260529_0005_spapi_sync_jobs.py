"""add spapi sync jobs

Revision ID: 20260529_0005
Revises: 20260529_0004
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0005"
down_revision = "20260529_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spapi_sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("amazon_authorization_id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=True),
        sa.Column("internal_report_type", sa.String(length=80), nullable=False),
        sa.Column("amazon_report_type", sa.String(length=120), nullable=False),
        sa.Column("date_range_start", sa.Date(), nullable=False),
        sa.Column("date_range_end", sa.Date(), nullable=False),
        sa.Column("report_options_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("amazon_report_id", sa.String(length=160), nullable=True),
        sa.Column("amazon_report_document_id", sa.String(length=160), nullable=True),
        sa.Column("download_path", sa.String(length=500), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["amazon_authorization_id"], ["amazon_authorizations.id"]),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplaces.id"]),
        sa.ForeignKeyConstraint(["seller_account_id"], ["seller_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_spapi_sync_jobs_seller_account_id",
        "spapi_sync_jobs",
        ["seller_account_id"],
    )
    op.create_index("ix_spapi_sync_jobs_marketplace_id", "spapi_sync_jobs", ["marketplace_id"])
    op.create_index(
        "ix_spapi_sync_jobs_amazon_authorization_id",
        "spapi_sync_jobs",
        ["amazon_authorization_id"],
    )
    op.create_index("ix_spapi_sync_jobs_import_job_id", "spapi_sync_jobs", ["import_job_id"])
    op.create_index(
        "ix_spapi_sync_jobs_internal_report_type",
        "spapi_sync_jobs",
        ["internal_report_type"],
    )
    op.create_index(
        "ix_spapi_sync_jobs_amazon_report_type",
        "spapi_sync_jobs",
        ["amazon_report_type"],
    )
    op.create_index("ix_spapi_sync_jobs_status", "spapi_sync_jobs", ["status"])
    op.create_index(
        "ix_spapi_sync_jobs_amazon_report_id",
        "spapi_sync_jobs",
        ["amazon_report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_spapi_sync_jobs_amazon_report_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_status", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_amazon_report_type", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_internal_report_type", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_import_job_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_amazon_authorization_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_marketplace_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_seller_account_id", table_name="spapi_sync_jobs")
    op.drop_table("spapi_sync_jobs")
