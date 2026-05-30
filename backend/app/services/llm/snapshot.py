from app.schemas.reports import DailyReportDocument


def build_llm_snapshot(report: DailyReportDocument) -> dict[str, object]:
    evidence_ids = [
        (
            f"store:{summary.seller_account_id}:marketplace:"
            f"{summary.marketplace_id}:{report.report_date.isoformat()}"
        )
        for summary in report.store_summaries
    ]
    if not evidence_ids:
        evidence_ids = [f"report:{report.report_date.isoformat()}"]
    evidence_ids.extend(
        f"trend:{point.period_label}:{point.currency}" for point in report.trend
    )
    evidence_ids.extend(
        f"sku:{item.sku}:{item.currency}" for item in report.sku_performance
    )
    return {
        "report_date": report.report_date.isoformat(),
        "data_source": report.data_source,
        "totals": {key: str(value) for key, value in report.totals.items()},
        "totals_by_currency": [
            total.model_dump(mode="json") for total in report.totals_by_currency
        ],
        "store_summaries": [summary.model_dump(mode="json") for summary in report.store_summaries],
        "trend": [point.model_dump(mode="json") for point in report.trend],
        "sku_performance": [item.model_dump(mode="json") for item in report.sku_performance],
        "warnings": report.warnings,
        "evidence_ids": evidence_ids,
    }
