from pathlib import Path

from app.domain.enums import ReportType
from app.services.imports.parser import parse_report_file
from app.services.imports.schema_registry import detect_schema

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_business_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "business_report.csv")
    schema = detect_schema(ReportType.BUSINESS_REPORT, parsed.headers)

    assert schema.version == "business_report.v1"
    assert parsed.row_count == 1


def test_detects_inventory_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "inventory_report.csv")
    schema = detect_schema(ReportType.INVENTORY_REPORT, parsed.headers)

    assert schema.version == "inventory_report.v1"


def test_detects_ads_search_term_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "ads_search_term_report.csv")
    schema = detect_schema(ReportType.ADS_SEARCH_TERM_REPORT, parsed.headers)

    assert schema.version == "ads_search_term_report.v1"
    assert parsed.sample_rows[0]["Search Term"] == "coffee grinder"
