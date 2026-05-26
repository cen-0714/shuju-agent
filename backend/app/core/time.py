from datetime import UTC, date, datetime

from app.domain.enums import DataStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


def classify_data_status(report_date: date, today: date | None = None) -> DataStatus:
    current_day = today or utc_now().date()
    age_days = (current_day - report_date).days
    if age_days <= 0:
        return DataStatus.PRELIMINARY
    if age_days <= 2:
        return DataStatus.STABLE
    return DataStatus.FINAL


def date_range_days(start: date, end: date) -> int:
    return (end - start).days + 1
