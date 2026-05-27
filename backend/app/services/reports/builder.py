from datetime import date
from decimal import Decimal

from app.schemas.reports import DailyReportDocument, StoreDailySummary


def build_daily_report(
    *,
    report_date: date,
    store_summaries: list[StoreDailySummary],
    warnings: list[str],
) -> DailyReportDocument:
    totals = {
        "ordered_product_sales": sum(
            (summary.ordered_product_sales for summary in store_summaries),
            Decimal("0"),
        ),
        "units_ordered": sum(
            (Decimal(summary.units_ordered) for summary in store_summaries),
            Decimal("0"),
        ),
        "ad_spend": sum((summary.ad_spend for summary in store_summaries), Decimal("0")),
        "ad_sales": sum((summary.ad_sales for summary in store_summaries), Decimal("0")),
    }
    return DailyReportDocument(
        report_date=report_date,
        store_summaries=store_summaries,
        totals=totals,
        warnings=warnings,
    )
