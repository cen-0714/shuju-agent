from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedAdsSearchTermRow:
    report_date: date
    campaign_name: str
    search_term: str
    impressions: int
    clicks: int
    spend: Decimal
    attributed_sales: Decimal
    attributed_orders: int


def normalize_ads_search_term_row(row: dict[str, str]) -> NormalizedAdsSearchTermRow:
    return NormalizedAdsSearchTermRow(
        report_date=date.fromisoformat(row["Date"]),
        campaign_name=row["Campaign Name"],
        search_term=row["Search Term"],
        impressions=int(row.get("Impressions") or 0),
        clicks=int(row.get("Clicks") or 0),
        spend=Decimal(row.get("Spend") or "0"),
        attributed_sales=Decimal(row.get("7 Day Total Sales") or "0"),
        attributed_orders=int(row.get("7 Day Total Orders (#)") or 0),
    )
