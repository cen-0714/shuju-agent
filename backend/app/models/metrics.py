from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MetricDefinition(TimestampMixin, Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(120))
    formula: Mapped[str] = mapped_column(Text)
    source_fields: Mapped[str] = mapped_column(Text)
    time_grain: Mapped[str] = mapped_column(String(40))
    currency_rule: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))

    __table_args__ = (UniqueConstraint("metric_name", "version"),)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    metric_date: Mapped[date] = mapped_column(Date)
    metric_name: Mapped[str] = mapped_column(String(120))
    metric_value: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    metric_version: Mapped[str] = mapped_column(String(40))
    data_status: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        UniqueConstraint("seller_account_id", "marketplace_id", "metric_date", "metric_name"),
    )
