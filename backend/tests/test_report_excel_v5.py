from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.schemas.reports import DailyReportDocument, StoreDailySummary
from app.services.reports.excel import write_daily_report_excel


def test_v5_excel_contains_ai_and_sync_sheets(tmp_path: Path) -> None:
    report = DailyReportDocument(
        report_date=date(2026, 5, 20),
        store_summaries=[
            StoreDailySummary(
                seller_account_id=1,
                seller_name="US Store",
                marketplace_id="ATVPDKIKX0DER",
                ordered_product_sales=Decimal("125.50"),
                units_ordered=5,
                ad_spend=Decimal("0"),
                ad_sales=Decimal("0"),
                acos=Decimal("0"),
                data_status="stable",
            )
        ],
        totals={"ordered_product_sales": Decimal("125.50"), "units_ordered": Decimal("5")},
        warnings=["No freshness warnings."],
        llm_analysis={
            "summary": "Sales are stable.",
            "findings": [
                {
                    "title": "Review SKU movement",
                    "severity": "warning",
                    "evidence_refs": ["store:1:marketplace:ATVPDKIKX0DER:2026-05-20"],
                    "reasoning": "SKU sales changed.",
                    "recommended_human_actions": ["Review SKU before changing anything."],
                    "human_review_required": True,
                }
            ],
            "data_quality_notes": ["No freshness warnings."],
        },
        sync_sources=[
            {
                "source": "sp_api",
                "report_type": "business_report",
                "raw_file_checksum": "abc123",
            }
        ],
    )
    output_path = tmp_path / "report.xlsx"

    write_daily_report_excel(report, output_path)

    workbook = pd.ExcelFile(output_path)
    assert set(workbook.sheet_names) >= {
        "Overview",
        "Store Summary",
        "AI Insights",
        "Action Checklist",
        "Data Warnings",
        "Sync Jobs",
    }
