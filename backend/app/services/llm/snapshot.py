from app.schemas.reports import DailyReportDocument


def build_llm_snapshot(report: DailyReportDocument) -> dict[str, object]:
    return {
        "report_date": report.report_date.isoformat(),
        "totals": {key: str(value) for key, value in report.totals.items()},
        "store_summaries": [summary.model_dump(mode="json") for summary in report.store_summaries],
        "warnings": report.warnings,
        "evidence_ids": [f"report:{report.report_date.isoformat()}"],
    }
