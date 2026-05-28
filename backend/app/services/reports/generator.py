import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.storage import LocalStorageBackend
from app.domain.enums import LLMStatus, ReportKind, ReportScopeType, ReportStatus
from app.models.normalized import NormalizedBusinessDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, SellerAccount
from app.schemas.reports import GenerateReportRequest, StoreDailySummary
from app.services.reports.builder import build_daily_report
from app.services.reports.excel import write_daily_report_excel
from app.services.reports.markdown import render_daily_report_markdown
from app.services.settings import ensure_default_organization


@dataclass
class _StoreAggregate:
    seller_account_id: int
    seller_name: str
    marketplace_key: str
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0
    data_status: str = "stable"


def generate_report(
    *,
    session: Session,
    storage: LocalStorageBackend,
    request: GenerateReportRequest,
) -> DailyReport:
    _validate_request(request)
    rows = _query_business_rows(session, request)
    if not rows:
        raise ValueError("no business data for requested report scope")

    summaries = _build_store_summaries(rows)
    document = build_daily_report(
        report_date=request.report_start_date,
        store_summaries=summaries,
        warnings=[],
    )
    markdown = render_daily_report_markdown(document)
    report_token = uuid4().hex
    markdown_path = f"reports/markdown/{report_token}.md"
    excel_path = f"reports/excel/{report_token}.xlsx"
    markdown_absolute = storage.resolve_path(markdown_path)
    markdown_absolute.parent.mkdir(parents=True, exist_ok=True)
    markdown_absolute.write_text(markdown, encoding="utf-8")
    write_daily_report_excel(document, storage.resolve_path(excel_path))

    organization = _resolve_organization(session, request)
    report_date = (
        request.report_start_date
        if request.report_kind == ReportKind.SINGLE_DAY
        else None
    )
    report = DailyReport(
        organization=organization,
        scope_type=request.scope_type.value,
        seller_account_id=request.seller_account_id,
        marketplace_id=request.marketplace_id,
        report_kind=request.report_kind.value,
        report_date=report_date,
        report_start_date=request.report_start_date,
        report_end_date=request.report_end_date,
        report_version=_next_report_version(session, organization.id, report_date),
        status=ReportStatus.ACTIVE.value,
        data_version=_data_version(rows),
        metric_definition_version="v1",
        prompt_version="v1",
        model_name="deterministic",
        report_json=json.dumps(document.model_dump(mode="json"), ensure_ascii=False),
        markdown=markdown,
        markdown_path=markdown_path,
        excel_path=excel_path,
        llm_status=LLMStatus.SKIPPED.value,
    )
    session.add(report)
    session.flush()
    return report


def _validate_request(request: GenerateReportRequest) -> None:
    if request.report_start_date > request.report_end_date:
        raise ValueError("report_start_date cannot be after report_end_date")
    if request.report_kind == ReportKind.SINGLE_DAY and (
        request.report_start_date != request.report_end_date
    ):
        raise ValueError("single_day reports require the same start and end date")
    if request.scope_type == ReportScopeType.SINGLE_STORE and (
        request.seller_account_id is None or request.marketplace_id is None
    ):
        raise ValueError("single_store reports require seller_account_id and marketplace_id")


def _query_business_rows(
    session: Session,
    request: GenerateReportRequest,
) -> list[NormalizedBusinessDaily]:
    query = select(NormalizedBusinessDaily).where(
        NormalizedBusinessDaily.report_date >= request.report_start_date,
        NormalizedBusinessDaily.report_date <= request.report_end_date,
    )
    if request.scope_type == ReportScopeType.SINGLE_STORE:
        query = query.where(
            NormalizedBusinessDaily.seller_account_id == request.seller_account_id,
            NormalizedBusinessDaily.marketplace_id == request.marketplace_id,
        )
    return list(session.scalars(query))


def _build_store_summaries(rows: list[NormalizedBusinessDaily]) -> list[StoreDailySummary]:
    grouped: dict[tuple[int, int], _StoreAggregate] = {}
    for row in rows:
        key = (row.seller_account_id, row.marketplace_id)
        aggregate = grouped.get(key)
        if aggregate is None:
            aggregate = _StoreAggregate(
                seller_account_id=row.seller_account_id,
                seller_name=row.seller_account.display_name,
                marketplace_key=row.marketplace.marketplace_id,
                data_status=row.raw_dataset.data_status,
            )
            grouped[key] = aggregate
        aggregate.ordered_product_sales += row.ordered_product_sales
        aggregate.units_ordered += row.units_ordered

    return [
        StoreDailySummary(
            seller_account_id=aggregate.seller_account_id,
            seller_name=aggregate.seller_name,
            marketplace_id=aggregate.marketplace_key,
            ordered_product_sales=aggregate.ordered_product_sales,
            units_ordered=aggregate.units_ordered,
            ad_spend=Decimal("0"),
            ad_sales=Decimal("0"),
            acos=Decimal("0"),
            data_status=aggregate.data_status,
        )
        for aggregate in sorted(grouped.values(), key=lambda item: item.seller_name)
    ]


def _resolve_organization(session: Session, request: GenerateReportRequest):
    if request.scope_type == ReportScopeType.SINGLE_STORE and request.seller_account_id is not None:
        seller_account = session.get(SellerAccount, request.seller_account_id)
        if seller_account is None:
            raise ValueError("seller account not found")
        if request.marketplace_id is not None:
            marketplace = session.get(Marketplace, request.marketplace_id)
            if marketplace is None or marketplace.seller_account_id != seller_account.id:
                raise ValueError("marketplace not found")
        return seller_account.organization
    return ensure_default_organization(session)


def _next_report_version(session: Session, organization_id: int, report_date: date | None) -> int:
    query = select(func.max(DailyReport.report_version)).where(
        DailyReport.organization_id == organization_id
    )
    if report_date is None:
        query = query.where(DailyReport.report_date.is_(None))
    else:
        query = query.where(DailyReport.report_date == report_date)
    current_version = session.scalar(query) or 0
    return current_version + 1


def _data_version(rows: list[NormalizedBusinessDaily]) -> str:
    source = "|".join(sorted({row.raw_dataset.data_version for row in rows}))
    digest = sha256(source.encode("utf-8")).hexdigest()[:16]
    return f"v2:{digest}"
