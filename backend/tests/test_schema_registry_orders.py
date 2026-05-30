import pytest

from app.core.errors import UnknownSchemaError
from app.domain.enums import ReportType
from app.services.imports.schema_registry import detect_schema


def test_detect_schema_matches_orders_v1() -> None:
    headers = [
        "amazon-order-id",
        "purchase-date",
        "sku",
        "asin",
        "product-name",
        "quantity",
        "currency",
        "item-price",
        "order-status",
    ]

    schema = detect_schema(ReportType.ORDERS_REPORT, headers)

    assert schema.version == "orders.v1"
    assert schema.report_type == ReportType.ORDERS_REPORT


def test_detect_schema_orders_missing_required_column_raises() -> None:
    headers = ["purchase-date", "sku", "quantity"]  # missing currency, order-status

    with pytest.raises(UnknownSchemaError):
        detect_schema(ReportType.ORDERS_REPORT, headers)


@pytest.mark.parametrize("missing_column", ["amazon-order-id", "item-price"])
def test_detect_schema_orders_requires_order_id_and_item_price(missing_column: str) -> None:
    headers = [
        "amazon-order-id",
        "purchase-date",
        "sku",
        "asin",
        "product-name",
        "quantity",
        "currency",
        "item-price",
        "order-status",
    ]
    headers.remove(missing_column)

    with pytest.raises(UnknownSchemaError):
        detect_schema(ReportType.ORDERS_REPORT, headers)
