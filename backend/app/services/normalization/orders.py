from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation


@dataclass(frozen=True)
class NormalizedOrderRow:
    report_date: date
    sku: str
    asin: str | None
    product_name: str | None
    currency: str
    units_ordered: int
    ordered_product_sales: Decimal
    order_count: int


def normalize_order_rows(rows: list[dict[str, str]]) -> list[NormalizedOrderRow]:
    grouped: dict[tuple[date, str, str], dict[str, object]] = {}
    order_ids: dict[tuple[date, str, str], set[str]] = defaultdict(set)

    for row in rows:
        if (row.get("order-status") or "").strip().lower() == "cancelled":
            continue
        report_date = _parse_date(row.get("purchase-date"))
        if report_date is None:
            continue
        sku = (row.get("sku") or "").strip()
        currency = (row.get("currency") or "").strip().upper()
        if not sku or not currency:
            continue

        key = (report_date, sku, currency)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "asin": (row.get("asin") or "").strip() or None,
                "product_name": (row.get("product-name") or "").strip() or None,
                "units_ordered": 0,
                "ordered_product_sales": Decimal("0"),
            }
            grouped[key] = bucket
        bucket["units_ordered"] = int(bucket["units_ordered"]) + _safe_int(row.get("quantity"))
        bucket["ordered_product_sales"] = Decimal(
            bucket["ordered_product_sales"]
        ) + _safe_decimal(row.get("item-price"))
        amazon_order_id = (row.get("amazon-order-id") or "").strip()
        if amazon_order_id:
            order_ids[key].add(amazon_order_id)

    result: list[NormalizedOrderRow] = []
    for (report_date, sku, currency), bucket in grouped.items():
        result.append(
            NormalizedOrderRow(
                report_date=report_date,
                sku=sku,
                asin=bucket["asin"],
                product_name=bucket["product_name"],
                currency=currency,
                units_ordered=int(bucket["units_ordered"]),
                ordered_product_sales=Decimal(bucket["ordered_product_sales"]),
                order_count=len(order_ids[(report_date, sku, currency)]),
            )
        )
    return result


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _safe_int(value: str | None) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(Decimal(value))
    except (InvalidOperation, ValueError):
        return 0


def _safe_decimal(value: str | None) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(value)
    except InvalidOperation:
        return Decimal("0")
