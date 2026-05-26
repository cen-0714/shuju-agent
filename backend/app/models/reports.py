from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailyReport(TimestampMixin, Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    report_date: Mapped[date] = mapped_column(Date)
    report_version: Mapped[int] = mapped_column(default=1)
    data_version: Mapped[str] = mapped_column(String(120))
    metric_definition_version: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(120))
    report_json: Mapped[str] = mapped_column(Text)
    markdown: Mapped[str] = mapped_column(Text)
    excel_path: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("organization_id", "report_date", "report_version"),)
