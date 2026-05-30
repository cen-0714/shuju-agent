from datetime import date
from decimal import Decimal

from app.services.normalization.orders import normalize_order_rows


def _row(**kwargs: str) -> dict[str, str]:
    base = {
        "amazon-order-id": "702-1",
        "purchase-date": "2026-05-28T10:00:00+00:00",
        "sku": "SKU-1",
        "asin": "B0AAA",
        "product-name": "Glass Globe",
        "quantity": "1",
        "currency": "USD",
        "item-price": "10.00",
        "order-status": "Shipped",
    }
    base.update(kwargs)
    return base


def test_aggregates_same_day_sku_currency() -> None:
    rows = [
        _row(**{"amazon-order-id": "A", "quantity": "2", "item-price": "20.00"}),
        _row(**{"amazon-order-id": "A", "quantity": "1", "item-price": "10.00"}),
        _row(**{"amazon-order-id": "B", "quantity": "3", "item-price": "30.00"}),
    ]
    result = normalize_order_rows(rows)

    assert len(result) == 1
    row = result[0]
    assert row.report_date == date(2026, 5, 28)
    assert row.sku == "SKU-1"
    assert row.currency == "USD"
    assert row.units_ordered == 6
    assert row.ordered_product_sales == Decimal("60.00")
    assert row.order_count == 2  # distinct amazon-order-id A, B


def test_excludes_cancelled_orders() -> None:
    rows = [
        _row(**{"order-status": "Cancelled", "quantity": "5", "item-price": "50.00"}),
        _row(**{"order-status": "Shipped", "quantity": "1", "item-price": "10.00"}),
    ]
    result = normalize_order_rows(rows)

    assert len(result) == 1
    assert result[0].units_ordered == 1
    assert result[0].ordered_product_sales == Decimal("10.00")


def test_separates_by_currency() -> None:
    rows = [
        _row(**{"amazon-order-id": "A", "currency": "USD", "item-price": "10.00"}),
        _row(**{"amazon-order-id": "B", "currency": "CAD", "item-price": "40.00"}),
    ]
    result = normalize_order_rows(rows)

    by_currency = {r.currency: r for r in result}
    assert set(by_currency) == {"USD", "CAD"}
    assert by_currency["USD"].ordered_product_sales == Decimal("10.00")
    assert by_currency["CAD"].ordered_product_sales == Decimal("40.00")


def test_handles_empty_item_price() -> None:
    rows = [_row(**{"item-price": ""})]
    result = normalize_order_rows(rows)

    assert result[0].ordered_product_sales == Decimal("0")
