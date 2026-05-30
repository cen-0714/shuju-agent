from dataclasses import dataclass


@dataclass(frozen=True)
class SPAPIReportType:
    internal_report_type: str
    amazon_report_type: str
    display_name: str
    role_group: str
    source: str
    output_format: str
    parser_version: str
    normalizer_version: str
    status: str
    pii_risk: str
    notes: str


REPORT_TYPES = {
    "business_sales_traffic": SPAPIReportType(
        internal_report_type="business_sales_traffic",
        amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
        display_name="Sales and Traffic Business Report",
        role_group="Brand Analytics",
        source="sp_api_reports",
        output_format="json",
        parser_version="sales_and_traffic.v1",
        normalizer_version="business_report.v1",
        status="enabled",
        pii_risk="none",
        notes="V5 first supported SP-API report. Does not include buyer PII.",
    ),
    "orders_by_date": SPAPIReportType(
        internal_report_type="orders_by_date",
        amazon_report_type="GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL",
        display_name="All Orders Report (by order date)",
        role_group="Product Listing, Pricing, Inventory and Order Tracking",
        source="sp_api_reports",
        output_format="tsv",
        parser_version="orders.v1",
        normalizer_version="orders.v1",
        status="enabled",
        pii_risk="low",
        notes=(
            "Phase 1 primary data source. Buyer address/PII columns are dropped "
            "during normalization; only SKU/quantity/amount/status are retained."
        ),
    ),
    "open_listings": SPAPIReportType(
        internal_report_type="open_listings",
        amazon_report_type="GET_FLAT_FILE_OPEN_LISTINGS_DATA",
        display_name="Open Listings Report",
        role_group="Product Listing, Pricing, Inventory and Order Tracking",
        source="sp_api_reports",
        output_format="tsv",
        parser_version="open_listings.v1",
        normalizer_version="inventory_report.v1",
        status="disabled",
        pii_risk="none",
        notes="Registered but blocked until parser and normalization are implemented.",
    ),
    "all_listings": SPAPIReportType(
        internal_report_type="all_listings",
        amazon_report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        display_name="All Listings Report",
        role_group="Product Listing, Pricing, Inventory and Order Tracking",
        source="sp_api_reports",
        output_format="tsv",
        parser_version="all_listings.v1",
        normalizer_version="inventory_report.v1",
        status="disabled",
        pii_risk="none",
        notes="Registered but blocked until parser and normalization are implemented.",
    ),
}


class ReportTypeNotFoundError(Exception):
    pass


class ReportTypeDisabledError(Exception):
    pass


def list_report_types() -> list[SPAPIReportType]:
    return list(REPORT_TYPES.values())


def get_enabled_report_types() -> list[SPAPIReportType]:
    return [item for item in REPORT_TYPES.values() if item.status == "enabled"]


def get_report_type(internal_report_type: str) -> SPAPIReportType:
    try:
        return REPORT_TYPES[internal_report_type]
    except KeyError as exc:
        message = f"SP-API report type not found: {internal_report_type}"
        raise ReportTypeNotFoundError(message) from exc


def require_enabled_report_type(internal_report_type: str) -> SPAPIReportType:
    report_type = get_report_type(internal_report_type)
    if report_type.status != "enabled":
        raise ReportTypeDisabledError(f"SP-API report type is disabled: {internal_report_type}")
    return report_type
