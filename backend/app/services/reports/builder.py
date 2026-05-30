from datetime import date
from decimal import Decimal

from app.schemas.reports import (
    CurrencyTotals,
    DailyReportDocument,
    SkuPerformance,
    StoreDailySummary,
    TrendPoint,
)


def build_daily_report(
    *,
    report_date: date,
    store_summaries: list[StoreDailySummary],
    warnings: list[str],
    data_source: str = "business",
    trend: list[TrendPoint] | None = None,
    sku_performance: list[SkuPerformance] | None = None,
) -> DailyReportDocument:
    totals_by_currency = _build_currency_totals(store_summaries)
    totals = {
        "units_ordered": sum(
            (Decimal(summary.units_ordered) for summary in store_summaries),
            Decimal("0"),
        ),
        "ad_spend": sum((summary.ad_spend for summary in store_summaries), Decimal("0")),
        "ad_sales": sum((summary.ad_sales for summary in store_summaries), Decimal("0")),
    }
    if not totals_by_currency:
        totals["ordered_product_sales"] = sum(
            (summary.ordered_product_sales for summary in store_summaries),
            Decimal("0"),
        )
    return DailyReportDocument(
        report_date=report_date,
        store_summaries=store_summaries,
        totals=totals,
        totals_by_currency=totals_by_currency,
        warnings=warnings,
        data_source=data_source,
        trend=trend or [],
        sku_performance=sku_performance or [],
    )


def _build_currency_totals(store_summaries: list[StoreDailySummary]) -> list[CurrencyTotals]:
    grouped: dict[str, dict[str, Decimal]] = {}
    for summary in store_summaries:
        if not summary.currency:
            continue
        bucket = grouped.setdefault(
            summary.currency,
            {"ordered_product_sales": Decimal("0"), "units_ordered": Decimal("0")},
        )
        bucket["ordered_product_sales"] += summary.ordered_product_sales
        bucket["units_ordered"] += Decimal(summary.units_ordered)
    return [
        CurrencyTotals(
            currency=currency,
            ordered_product_sales=totals["ordered_product_sales"],
            units_ordered=int(totals["units_ordered"]),
        )
        for currency, totals in sorted(grouped.items())
    ]
