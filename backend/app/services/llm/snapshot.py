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
    return {
        "report_date": report.report_date.isoformat(),
        "totals": {key: str(value) for key, value in report.totals.items()},
        "store_summaries": [summary.model_dump(mode="json") for summary in report.store_summaries],
        "warnings": report.warnings,
        "evidence_ids": evidence_ids,
    }
