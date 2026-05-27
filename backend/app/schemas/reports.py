from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StoreDailySummary(BaseModel):
    seller_account_id: int
    seller_name: str
    marketplace_id: str
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0
    ad_spend: Decimal = Decimal("0")
    ad_sales: Decimal = Decimal("0")
    acos: Decimal = Decimal("0")
    data_status: str


class DailyReportDocument(BaseModel):
    report_date: date
    store_summaries: list[StoreDailySummary]
    totals: dict[str, Decimal]
    warnings: list[str]
