from datetime import date
from decimal import Decimal
from pathlib import Path

from app.schemas.reports import StoreDailySummary
from app.services.reports.builder import build_daily_report
from app.services.reports.excel import write_daily_report_excel
from app.services.reports.markdown import render_daily_report_markdown


def test_build_daily_report_contains_store_summary() -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[
            StoreDailySummary(
                seller_account_id=1,
                seller_name="US Store A",
                marketplace_id="ATVPDKIKX0DER",
                ordered_product_sales=Decimal("240.00"),
                units_ordered=12,
                ad_spend=Decimal("32.50"),
                ad_sales=Decimal("120.00"),
                acos=Decimal("0.2708"),
                data_status="stable",
            )
        ],
        warnings=["inventory report missing"],
    )

    assert report.report_date.isoformat() == "2026-05-25"
    assert report.totals["ordered_product_sales"] == Decimal("240.00")
    assert report.warnings == ["inventory report missing"]


def test_render_daily_report_markdown() -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[],
        warnings=[],
    )

    markdown = render_daily_report_markdown(report)

    assert "# Daily Amazon Report - 2026-05-25" in markdown
    assert "Data Freshness" in markdown


def test_write_daily_report_excel(tmp_path: Path) -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[],
        warnings=[],
    )
    output = tmp_path / "daily.xlsx"

    write_daily_report_excel(report, output)

    assert output.exists()
    assert output.stat().st_size > 0
