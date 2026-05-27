from datetime import date

from app.core.time import classify_data_status
from app.domain.enums import DataStatus


def freshness_for_report_date(report_date: date, today: date | None = None) -> DataStatus:
    return classify_data_status(report_date, today=today)
