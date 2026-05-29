from pathlib import Path

import pandas as pd

from app.schemas.reports import DailyReportDocument


def write_daily_report_excel(report: DailyReportDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [summary.model_dump(mode="json") for summary in report.store_summaries]
    overview = [{"metric": key, "value": str(value)} for key, value in report.totals.items()]
    totals = overview
    warnings = [{"warning": warning} for warning in report.warnings]
    ai = report.llm_analysis or {}
    findings = ai.get("findings", []) if isinstance(ai, dict) else []
    data_quality_notes = ai.get("data_quality_notes", []) if isinstance(ai, dict) else []
    data_warnings = warnings + [{"warning": str(note)} for note in data_quality_notes]
    actions = [
        {
            "title": finding.get("title"),
            "action": action,
            "human_review_required": finding.get("human_review_required"),
        }
        for finding in findings
        for action in finding.get("recommended_human_actions", [])
    ]

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(overview).to_excel(writer, sheet_name="Overview", index=False)
        pd.DataFrame(rows).to_excel(writer, sheet_name="Store Summary", index=False)
        pd.DataFrame(totals).to_excel(writer, sheet_name="Totals", index=False)
        pd.DataFrame(findings).to_excel(writer, sheet_name="AI Insights", index=False)
        pd.DataFrame(actions).to_excel(writer, sheet_name="Action Checklist", index=False)
        pd.DataFrame(data_warnings).to_excel(writer, sheet_name="Data Warnings", index=False)
        pd.DataFrame(warnings).to_excel(writer, sheet_name="Warnings", index=False)
        pd.DataFrame(report.sync_sources).to_excel(writer, sheet_name="Sync Jobs", index=False)
