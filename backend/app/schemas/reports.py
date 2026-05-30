from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ReportKind, ReportScopeType


class StoreDailySummary(BaseModel):
    seller_account_id: int
    seller_name: str
    marketplace_id: str
    currency: str | None = None
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0
    ad_spend: Decimal = Decimal("0")
    ad_sales: Decimal = Decimal("0")
    acos: Decimal = Decimal("0")
    data_status: str


class TrendPoint(BaseModel):
    period_label: str
    period_start: date
    period_end: date
    currency: str
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0
    order_count: int = 0


class SkuPerformance(BaseModel):
    sku: str
    asin: str | None = None
    product_name: str | None = None
    currency: str
    units_ordered: int = 0
    ordered_product_sales: Decimal = Decimal("0")


class CurrencyTotals(BaseModel):
    currency: str
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0


class DailyReportDocument(BaseModel):
    report_date: date
    store_summaries: list[StoreDailySummary]
    totals: dict[str, Decimal]
    totals_by_currency: list[CurrencyTotals] = Field(default_factory=list)
    warnings: list[str]
    data_source: Literal["orders", "business"] = "business"
    trend: list[TrendPoint] = Field(default_factory=list)
    sku_performance: list[SkuPerformance] = Field(default_factory=list)
    llm_analysis: dict[str, Any] | None = None
    sync_sources: list[dict[str, Any]] = Field(default_factory=list)


class GenerateReportRequest(BaseModel):
    scope_type: ReportScopeType
    report_kind: ReportKind
    report_start_date: date
    report_end_date: date
    data_source: Literal["orders", "business"] = "orders"
    seller_account_id: int | None = None
    marketplace_id: int | None = None


class DailyReportResponse(BaseModel):
    id: int
    scope_type: str
    report_kind: str
    report_start_date: date
    report_end_date: date
    status: str
    markdown: str
    excel_path: str | None
    llm_status: str
    llm_error: str | None

    model_config = ConfigDict(from_attributes=True)
