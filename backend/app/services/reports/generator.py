import json
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.storage import LocalStorageBackend
from app.domain.enums import LLMStatus, ReportKind, ReportScopeType, ReportStatus
from app.models.normalized import NormalizedBusinessDaily, NormalizedOrderDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, SellerAccount
from app.schemas.reports import (
    GenerateReportRequest,
    SkuPerformance,
    StoreDailySummary,
    TrendPoint,
)
from app.services.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.services.llm.provider import MockLLMProvider
from app.services.llm.snapshot import build_llm_snapshot
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
    if request.data_source == "orders":
        rows = _query_order_rows(session, request)
        if not rows:
            raise ValueError("no order data for requested report scope")
        summaries = _build_order_store_summaries(rows)
        document = build_daily_report(
            report_date=request.report_start_date,
            store_summaries=summaries,
            warnings=[],
            data_source="orders",
            trend=_build_trend(rows, request),
            sku_performance=_build_sku_performance(rows),
        )
    else:
        rows = _query_business_rows(session, request)
        if not rows:
            raise ValueError("no business data for requested report scope")
        summaries = _build_store_summaries(rows)
        document = build_daily_report(
            report_date=request.report_start_date,
            store_summaries=summaries,
            warnings=[],
        )
    settings = Settings()
    snapshot = build_llm_snapshot(document)
    if settings.LLM_PROVIDER == "mock":
        llm_output = MockLLMProvider().analyze(snapshot)
        llm_status = LLMStatus.SUCCEEDED.value
        llm_error = None
        model_name = "mock"
    else:
        llm_result = OpenAICompatibleLLMProvider(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
        ).analyze(snapshot)
        llm_output = llm_result.output
        llm_status = llm_result.status
        llm_error = llm_result.error
        model_name = settings.LLM_MODEL
    document.llm_analysis = llm_output
    document.sync_sources = _build_sync_sources(rows)

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
        prompt_version="daily_report_v1",
        model_name=model_name,
        report_json=json.dumps(document.model_dump(mode="json"), ensure_ascii=False),
        markdown=markdown,
        markdown_path=markdown_path,
        excel_path=excel_path,
        llm_status=llm_status,
        llm_error=llm_error,
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


def _query_order_rows(
    session: Session,
    request: GenerateReportRequest,
) -> list[NormalizedOrderDaily]:
    query = select(NormalizedOrderDaily).where(
        NormalizedOrderDaily.report_date >= request.report_start_date,
        NormalizedOrderDaily.report_date <= request.report_end_date,
    )
    if request.scope_type == ReportScopeType.SINGLE_STORE:
        query = query.where(
            NormalizedOrderDaily.seller_account_id == request.seller_account_id,
            NormalizedOrderDaily.marketplace_id == request.marketplace_id,
        )
    return list(session.scalars(query))


def _build_order_store_summaries(
    rows: list[NormalizedOrderDaily],
) -> list[StoreDailySummary]:
    grouped: dict[tuple[int, int, str], dict[str, object]] = {}
    for row in rows:
        key = (row.seller_account_id, row.marketplace_id, row.currency)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "seller_name": row.seller_account.display_name,
                "marketplace_key": row.marketplace.marketplace_id,
                "data_status": row.raw_dataset.data_status,
                "ordered_product_sales": Decimal("0"),
                "units_ordered": 0,
            }
            grouped[key] = bucket
        bucket["ordered_product_sales"] = (
            Decimal(bucket["ordered_product_sales"]) + row.ordered_product_sales
        )
        bucket["units_ordered"] = int(bucket["units_ordered"]) + row.units_ordered

    summaries: list[StoreDailySummary] = []
    for (seller_account_id, _marketplace_id, currency), bucket in grouped.items():
        summaries.append(
            StoreDailySummary(
                seller_account_id=seller_account_id,
                seller_name=str(bucket["seller_name"]),
                marketplace_id=str(bucket["marketplace_key"]),
                currency=currency,
                ordered_product_sales=Decimal(bucket["ordered_product_sales"]),
                units_ordered=int(bucket["units_ordered"]),
                data_status=str(bucket["data_status"]),
            )
        )
    return sorted(summaries, key=lambda item: (item.seller_name, item.currency or ""))


def _build_trend(
    rows: list[NormalizedOrderDaily],
    request: GenerateReportRequest,
) -> list[TrendPoint]:
    if request.report_kind == ReportKind.SINGLE_DAY:
        return _trend_by_granularity(rows, "day")
    points: list[TrendPoint] = []
    for granularity in ("day", "week", "month"):
        points.extend(_trend_by_granularity(rows, granularity))
    return points


def _trend_by_granularity(
    rows: list[NormalizedOrderDaily],
    granularity: str,
) -> list[TrendPoint]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        label, period_start, period_end = _period_bounds(row.report_date, granularity)
        key = (label, row.currency)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "period_start": period_start,
                "period_end": period_end,
                "ordered_product_sales": Decimal("0"),
                "units_ordered": 0,
                "order_count": 0,
            }
            grouped[key] = bucket
        bucket["ordered_product_sales"] = (
            Decimal(bucket["ordered_product_sales"]) + row.ordered_product_sales
        )
        bucket["units_ordered"] = int(bucket["units_ordered"]) + row.units_ordered
        bucket["order_count"] = int(bucket["order_count"]) + row.order_count

    points = [
        TrendPoint(
            period_label=label,
            period_start=bucket["period_start"],  # type: ignore[arg-type]
            period_end=bucket["period_end"],  # type: ignore[arg-type]
            currency=currency,
            ordered_product_sales=Decimal(bucket["ordered_product_sales"]),
            units_ordered=int(bucket["units_ordered"]),
            order_count=int(bucket["order_count"]),
        )
        for (label, currency), bucket in grouped.items()
    ]
    return sorted(points, key=lambda item: (item.period_start, item.currency))


def _period_bounds(day: date, granularity: str) -> tuple[str, date, date]:
    if granularity == "day":
        return (f"D:{day.isoformat()}", day, day)
    if granularity == "week":
        iso_year, iso_week, iso_weekday = day.isocalendar()
        monday = day - timedelta(days=iso_weekday - 1)
        sunday = monday + timedelta(days=6)
        return (f"W:{iso_year}-W{iso_week:02d}", monday, sunday)
    # month
    first = day.replace(day=1)
    if day.month == 12:
        next_first = day.replace(year=day.year + 1, month=1, day=1)
    else:
        next_first = day.replace(month=day.month + 1, day=1)
    last = next_first - timedelta(days=1)
    return (f"M:{day.year}-{day.month:02d}", first, last)


def _build_sku_performance(
    rows: list[NormalizedOrderDaily],
) -> list[SkuPerformance]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (row.sku, row.currency)
        bucket = grouped.get(key)
        if bucket is None:
            bucket = {
                "asin": row.asin,
                "product_name": row.product_name,
                "units_ordered": 0,
                "ordered_product_sales": Decimal("0"),
            }
            grouped[key] = bucket
        bucket["units_ordered"] = int(bucket["units_ordered"]) + row.units_ordered
        bucket["ordered_product_sales"] = (
            Decimal(bucket["ordered_product_sales"]) + row.ordered_product_sales
        )

    performance = [
        SkuPerformance(
            sku=sku,
            asin=bucket["asin"],  # type: ignore[arg-type]
            product_name=bucket["product_name"],  # type: ignore[arg-type]
            currency=currency,
            units_ordered=int(bucket["units_ordered"]),
            ordered_product_sales=Decimal(bucket["ordered_product_sales"]),
        )
        for (sku, currency), bucket in grouped.items()
    ]
    return sorted(
        performance,
        key=lambda item: item.ordered_product_sales,
        reverse=True,
    )


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


def _build_sync_sources(rows: list[NormalizedBusinessDaily]) -> list[dict[str, object]]:
    seen: dict[int, dict[str, object]] = {}
    for row in rows:
        dataset = row.raw_dataset
        seen[dataset.id] = {
            "raw_dataset_id": dataset.id,
            "source": dataset.source,
            "report_type": dataset.report_type,
            "raw_file_path": dataset.raw_file_path,
            "raw_file_checksum": dataset.raw_file_checksum,
            "data_status": dataset.data_status,
        }
    return list(seen.values())
