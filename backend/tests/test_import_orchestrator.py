from datetime import date
from pathlib import Path

from app.domain.enums import DataStatus, ReportType
from app.services.imports.orchestrator import preview_manual_import


def test_preview_manual_import_returns_schema_and_rows() -> None:
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    preview = preview_manual_import(
        file_path=fixture,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
    )

    assert preview.detected_schema_version == "business_report.v1"
    assert preview.row_count == 1
    assert preview.required_columns_present is True
    assert preview.data_status == DataStatus.STABLE
