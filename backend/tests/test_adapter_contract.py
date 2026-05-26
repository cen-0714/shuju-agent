from datetime import date
from pathlib import Path

from app.domain.enums import DataSource, DataStatus, ReportType
from app.services.adapters.base import RawDatasetEnvelope
from app.services.adapters.manual_file import ManualFileAdapter


def test_raw_dataset_envelope_contains_required_fields() -> None:
    envelope = RawDatasetEnvelope(
        seller_account_id=1,
        marketplace_id=2,
        region="americas",
        source=DataSource.MANUAL_FILE,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        schema_version="business_report.v1",
        raw_file_path="storage/raw/business.csv",
        raw_file_checksum="abc123",
        row_count=3,
        data_status=DataStatus.STABLE,
        data_version="2026-05-25-1",
        source_generated_at=None,
    )

    assert envelope.source == DataSource.MANUAL_FILE
    assert envelope.report_type == ReportType.BUSINESS_REPORT


def test_manual_file_adapter_builds_envelope(tmp_path: Path) -> None:
    file_path = tmp_path / "business.csv"
    file_path.write_text("date,sessions\n2026-05-25,10\n", encoding="utf-8")

    adapter = ManualFileAdapter(storage_root=tmp_path)
    envelope = adapter.build_envelope(
        source_file=file_path,
        seller_account_id=1,
        marketplace_id=2,
        region="americas",
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        schema_version="business_report.v1",
        row_count=1,
        data_status=DataStatus.STABLE,
    )

    assert envelope.raw_file_checksum
    assert envelope.raw_file_path.endswith(".csv")
    assert envelope.data_version.startswith("2026-05-25")
