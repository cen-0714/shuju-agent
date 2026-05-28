from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class DailyReport(TimestampMixin, Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    seller_account_id: Mapped[int | None] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int | None] = mapped_column(ForeignKey("marketplaces.id"))
    scope_type: Mapped[str] = mapped_column(String(40), default="single_store")
    report_kind: Mapped[str] = mapped_column(String(40), default="single_day")
    report_date: Mapped[date | None] = mapped_column(Date)
    report_start_date: Mapped[date] = mapped_column(Date)
    report_end_date: Mapped[date] = mapped_column(Date)
    report_version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(40), default="active")
    data_version: Mapped[str] = mapped_column(String(120))
    metric_definition_version: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(120))
    report_json: Mapped[str] = mapped_column(Text)
    markdown: Mapped[str] = mapped_column(Text)
    markdown_path: Mapped[str | None] = mapped_column(String(500))
    excel_path: Mapped[str | None] = mapped_column(String(500))
    llm_status: Mapped[str] = mapped_column(String(40), default="skipped")
    llm_error: Mapped[str | None] = mapped_column(Text)

    organization = relationship("Organization")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")

    __table_args__ = (UniqueConstraint("organization_id", "report_date", "report_version"),)
