from app.services.amazon.report_types import get_enabled_report_types, get_report_type


def test_enabled_report_types_only_exposes_business_sales_traffic() -> None:
    enabled = get_enabled_report_types()

    assert [item.internal_report_type for item in enabled] == ["business_sales_traffic"]
    assert enabled[0].amazon_report_type == "GET_SALES_AND_TRAFFIC_REPORT"
    assert enabled[0].role_group == "Brand Analytics"
    assert enabled[0].pii_risk == "none"


def test_disabled_report_type_is_not_returned_as_enabled() -> None:
    open_listings = get_report_type("open_listings")

    assert open_listings.status == "disabled"
    assert all(item.internal_report_type != "open_listings" for item in get_enabled_report_types())
