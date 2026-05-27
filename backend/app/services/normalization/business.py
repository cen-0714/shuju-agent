from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedBusinessRow:
    report_date: date
    asin: str | None
    sku: str | None
    ordered_product_sales: Decimal
    units_ordered: int
    sessions: int
    page_views: int
    conversion_rate: Decimal | None
    buy_box_percentage: Decimal | None


def normalize_business_row(row: dict[str, str]) -> NormalizedBusinessRow:
    return NormalizedBusinessRow(
        report_date=date.fromisoformat(row["Date"]),
        asin=row.get("ASIN") or None,
        sku=row.get("SKU") or None,
        ordered_product_sales=Decimal(row.get("Ordered Product Sales") or "0"),
        units_ordered=int(row.get("Units Ordered") or 0),
        sessions=int(row.get("Sessions") or 0),
        page_views=int(row.get("Page Views") or 0),
        conversion_rate=_optional_decimal(row.get("Conversion Rate")),
        buy_box_percentage=_optional_decimal(row.get("Buy Box Percentage")),
    )


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(value)
