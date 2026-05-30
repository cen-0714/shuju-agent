from app.services.amazon.report_types import get_enabled_report_types, get_report_type


def test_enabled_report_types_include_business_sales_traffic() -> None:
    enabled = {item.internal_report_type: item for item in get_enabled_report_types()}

    assert "business_sales_traffic" in enabled
    sales_traffic = enabled["business_sales_traffic"]
    assert sales_traffic.amazon_report_type == "GET_SALES_AND_TRAFFIC_REPORT"
    assert sales_traffic.role_group == "Brand Analytics"
    assert sales_traffic.pii_risk == "none"


def test_orders_by_date_report_type_is_enabled() -> None:
    enabled = {item.internal_report_type: item for item in get_enabled_report_types()}

    assert "orders_by_date" in enabled
    orders = enabled["orders_by_date"]
    assert orders.amazon_report_type == "GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL"
    assert orders.output_format == "tsv"
    assert orders.parser_version == "orders.v1"
    assert orders.normalizer_version == "orders.v1"


def test_disabled_report_type_is_not_returned_as_enabled() -> None:
    open_listings = get_report_type("open_listings")

    assert open_listings.status == "disabled"
    assert all(item.internal_report_type != "open_listings" for item in get_enabled_report_types())
