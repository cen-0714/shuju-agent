from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedInventoryRow:
    sku: str
    asin: str
    fulfillment_channel: str | None
    available_quantity: int
    listing_status: str
    price: Decimal | None
    is_active_listing: bool


def normalize_inventory_row(row: dict[str, str]) -> NormalizedInventoryRow:
    status = row.get("status", "")
    return NormalizedInventoryRow(
        sku=row["sku"],
        asin=row["asin"],
        fulfillment_channel=row.get("fulfillment-channel") or None,
        available_quantity=int(row.get("quantity") or 0),
        listing_status=status,
        price=Decimal(row["price"]) if row.get("price") else None,
        is_active_listing=status.lower() == "active",
    )
