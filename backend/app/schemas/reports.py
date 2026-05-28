from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.domain.enums import ReportKind, ReportScopeType


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


class GenerateReportRequest(BaseModel):
    scope_type: ReportScopeType
    report_kind: ReportKind
    report_start_date: date
    report_end_date: date
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
