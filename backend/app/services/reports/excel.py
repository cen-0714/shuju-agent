from pathlib import Path

import pandas as pd

from app.schemas.reports import DailyReportDocument


def write_daily_report_excel(report: DailyReportDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [summary.model_dump(mode="json") for summary in report.store_summaries]
    totals = [{"metric": key, "value": str(value)} for key, value in report.totals.items()]
    warnings = [{"warning": warning} for warning in report.warnings]

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Store Summary", index=False)
        pd.DataFrame(totals).to_excel(writer, sheet_name="Totals", index=False)
        pd.DataFrame(warnings).to_excel(writer, sheet_name="Warnings", index=False)
