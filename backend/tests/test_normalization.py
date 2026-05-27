from decimal import Decimal

from app.services.normalization.ads import normalize_ads_search_term_row
from app.services.normalization.business import normalize_business_row
from app.services.normalization.inventory import normalize_inventory_row


def test_normalize_business_row() -> None:
    row = {
        "Date": "2026-05-25",
        "ASIN": "B0TESTASIN",
        "SKU": "SKU-1",
        "Sessions": "100",
        "Page Views": "180",
        "Units Ordered": "12",
        "Ordered Product Sales": "240.00",
        "Conversion Rate": "0.12",
        "Buy Box Percentage": "0.98",
    }

    normalized = normalize_business_row(row)

    assert normalized.report_date.isoformat() == "2026-05-25"
    assert normalized.ordered_product_sales == Decimal("240.00")
    assert normalized.units_ordered == 12


def test_normalize_inventory_row() -> None:
    row = {
        "sku": "SKU-1",
        "asin": "B0TESTASIN",
        "fulfillment-channel": "AMAZON_NA",
        "quantity": "22",
        "status": "Active",
        "price": "19.99",
    }

    normalized = normalize_inventory_row(row)

    assert normalized.sku == "SKU-1"
    assert normalized.available_quantity == 22
    assert normalized.is_active_listing is True


def test_normalize_ads_search_term_row() -> None:
    row = {
        "Date": "2026-05-25",
        "Campaign Name": "Campaign A",
        "Search Term": "coffee grinder",
        "Impressions": "1000",
        "Clicks": "40",
        "Spend": "32.50",
        "7 Day Total Sales": "120.00",
        "7 Day Total Orders (#)": "4",
    }

    normalized = normalize_ads_search_term_row(row)

    assert normalized.search_term == "coffee grinder"
    assert normalized.spend == Decimal("32.50")
    assert normalized.attributed_orders == 4
