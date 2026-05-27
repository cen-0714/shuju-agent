from dataclasses import dataclass

from app.core.errors import UnknownSchemaError
from app.domain.enums import ReportType


@dataclass(frozen=True)
class ReportSchema:
    version: str
    report_type: ReportType
    required_columns: set[str]
    aliases: dict[str, str]


SCHEMAS: dict[ReportType, list[ReportSchema]] = {
    ReportType.BUSINESS_REPORT: [
        ReportSchema(
            version="business_report.v1",
            report_type=ReportType.BUSINESS_REPORT,
            required_columns={"Date", "Sessions", "Units Ordered", "Ordered Product Sales"},
            aliases={
                "Date": "report_date",
                "ASIN": "asin",
                "SKU": "sku",
                "Sessions": "sessions",
                "Page Views": "page_views",
                "Units Ordered": "units_ordered",
                "Ordered Product Sales": "ordered_product_sales",
                "Conversion Rate": "conversion_rate",
                "Buy Box Percentage": "buy_box_percentage",
            },
        )
    ],
    ReportType.INVENTORY_REPORT: [
        ReportSchema(
            version="inventory_report.v1",
            report_type=ReportType.INVENTORY_REPORT,
            required_columns={"sku", "asin", "quantity", "status"},
            aliases={
                "sku": "sku",
                "asin": "asin",
                "fulfillment-channel": "fulfillment_channel",
                "quantity": "available_quantity",
                "status": "listing_status",
                "price": "price",
            },
        )
    ],
    ReportType.ADS_SEARCH_TERM_REPORT: [
        ReportSchema(
            version="ads_search_term_report.v1",
            report_type=ReportType.ADS_SEARCH_TERM_REPORT,
            required_columns={"Date", "Campaign Name", "Search Term", "Clicks", "Spend"},
            aliases={
                "Date": "report_date",
                "Campaign Name": "campaign_name",
                "Search Term": "search_term",
                "Impressions": "impressions",
                "Clicks": "clicks",
                "Spend": "spend",
                "7 Day Total Sales": "attributed_sales",
                "7 Day Total Orders (#)": "attributed_orders",
            },
        )
    ],
}


def detect_schema(report_type: ReportType, headers: list[str]) -> ReportSchema:
    header_set = set(headers)
    for schema in SCHEMAS.get(report_type, []):
        if schema.required_columns.issubset(header_set):
            return schema
    raise UnknownSchemaError(f"No schema matched report type {report_type}")
