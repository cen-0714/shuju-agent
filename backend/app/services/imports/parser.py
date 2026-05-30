import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.errors import UnsupportedFileTypeError


@dataclass(frozen=True)
class ParsedReportFile:
    headers: list[str]
    rows: list[dict[str, str]]
    row_count: int
    sample_rows: list[dict[str, str]]


def parse_report_file(path: Path) -> ParsedReportFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str).fillna("")
    elif suffix == ".tsv":
        frame = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str).fillna("")
    elif suffix == ".json":
        return _parse_sales_and_traffic_json(path)
    else:
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")

    rows = [
        {str(key): str(value) for key, value in row.items()}
        for row in frame.to_dict("records")
    ]
    return ParsedReportFile(
        headers=[str(column) for column in frame.columns],
        rows=rows,
        row_count=len(rows),
        sample_rows=rows[:5],
    )


def _parse_sales_and_traffic_json(path: Path) -> ParsedReportFile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    date_rows = payload.get("salesAndTrafficByDate") or []
    asin_rows = payload.get("salesAndTrafficByAsin") or []
    report_date = str(date_rows[0].get("date")) if date_rows else ""
    rows: list[dict[str, str]] = []
    for item in asin_rows:
        sales = item.get("salesByAsin") or {}
        traffic = item.get("trafficByAsin") or {}
        amount = (sales.get("orderedProductSales") or {}).get("amount") or "0"
        rows.append(
            {
                "Date": report_date,
                "ASIN": str(item.get("childAsin") or item.get("parentAsin") or ""),
                "SKU": str(item.get("sku") or ""),
                "Sessions": str(traffic.get("sessions") or 0),
                "Page Views": str(traffic.get("pageViews") or 0),
                "Units Ordered": str(sales.get("unitsOrdered") or 0),
                "Ordered Product Sales": str(amount),
                "Conversion Rate": str(traffic.get("unitSessionPercentage") or ""),
                "Buy Box Percentage": str(traffic.get("buyBoxPercentage") or ""),
            }
        )
    headers = [
        "Date",
        "ASIN",
        "SKU",
        "Sessions",
        "Page Views",
        "Units Ordered",
        "Ordered Product Sales",
        "Conversion Rate",
        "Buy Box Percentage",
    ]
    return ParsedReportFile(headers=headers, rows=rows, row_count=len(rows), sample_rows=rows[:5])
