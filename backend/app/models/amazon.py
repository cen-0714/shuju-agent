from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.imports import ImportJob
    from app.models.settings import Marketplace, SellerAccount


class AmazonAuthorization(TimestampMixin, Base):
    __tablename__ = "amazon_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    selling_partner_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    seller_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("seller_accounts.id"), nullable=True, index=True
    )
    lwa_client_id: Mapped[str] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    token_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    seller_account: Mapped["SellerAccount | None"] = relationship()


class SPAPISyncJob(TimestampMixin, Base):
    __tablename__ = "spapi_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"), index=True)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), index=True)
    amazon_authorization_id: Mapped[int] = mapped_column(
        ForeignKey("amazon_authorizations.id"), index=True
    )
    import_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_jobs.id"), nullable=True, index=True
    )
    internal_report_type: Mapped[str] = mapped_column(String(80), index=True)
    amazon_report_type: Mapped[str] = mapped_column(String(120), index=True)
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    report_options_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), index=True)
    amazon_report_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    amazon_report_document_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    download_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    seller_account: Mapped["SellerAccount"] = relationship()
    marketplace: Mapped["Marketplace"] = relationship()
    amazon_authorization: Mapped[AmazonAuthorization] = relationship()
    import_job: Mapped["ImportJob | None"] = relationship()
