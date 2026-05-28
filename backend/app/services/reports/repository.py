from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import ReportScopeType, ReportStatus
from app.models.imports import RawDataset
from app.models.reports import DailyReport


def mark_reports_stale_for_dataset(session: Session, dataset: RawDataset) -> int:
    query = select(DailyReport).where(
        DailyReport.status == ReportStatus.ACTIVE.value,
        DailyReport.report_start_date <= dataset.date_range_end,
        DailyReport.report_end_date >= dataset.date_range_start,
    )
    stale_count = 0
    for report in session.scalars(query):
        all_store_match = report.scope_type == ReportScopeType.ALL_STORES.value
        single_store_match = (
            report.scope_type == ReportScopeType.SINGLE_STORE.value
            and report.seller_account_id == dataset.seller_account_id
            and report.marketplace_id == dataset.marketplace_id
        )
        if all_store_match or single_store_match:
            report.status = ReportStatus.STALE.value
            stale_count += 1
    return stale_count
