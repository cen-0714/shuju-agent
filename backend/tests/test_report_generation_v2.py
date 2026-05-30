import json
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.domain.enums import DataSource, ReportKind, ReportScopeType, ReportStatus, ReportType
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedBusinessDaily
from app.models.settings import Marketplace, Organization, SellerAccount
from app.schemas.reports import GenerateReportRequest
from app.services.reports.generator import generate_report


def test_generate_single_store_single_day_report(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        seller, marketplace = _create_business_row(
            session,
            display_name="Store A",
            seller_id="SELLER-A",
            sales=Decimal("240.00"),
            units=12,
        )

        report = generate_report(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            request=GenerateReportRequest(
                scope_type=ReportScopeType.SINGLE_STORE,
                report_kind=ReportKind.SINGLE_DAY,
                report_start_date=date(2026, 5, 25),
                report_end_date=date(2026, 5, 25),
                data_source="business",
                seller_account_id=seller.id,
                marketplace_id=marketplace.id,
            ),
        )
        session.commit()

        body = json.loads(report.report_json)
        assert report.status == ReportStatus.ACTIVE.value
        assert report.scope_type == ReportScopeType.SINGLE_STORE.value
        assert report.report_kind == ReportKind.SINGLE_DAY.value
        assert report.markdown_path is not None
        assert report.excel_path is not None
        assert (tmp_path / report.markdown_path).exists()
        assert (tmp_path / report.excel_path).exists()
        assert body["totals"]["ordered_product_sales"] == "240.00"
        assert body["totals"]["units_ordered"] == "12"


def test_generate_all_stores_date_range_report(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        _create_business_row(
            session,
            display_name="Store A",
            seller_id="SELLER-A",
            sales=Decimal("240.00"),
            units=12,
        )
        _create_business_row(
            session,
            display_name="Store B",
            seller_id="SELLER-B",
            sales=Decimal("60.00"),
            units=3,
        )

        report = generate_report(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            request=GenerateReportRequest(
                scope_type=ReportScopeType.ALL_STORES,
                report_kind=ReportKind.DATE_RANGE,
                report_start_date=date(2026, 5, 25),
                report_end_date=date(2026, 5, 26),
                data_source="business",
            ),
        )
        session.commit()

        body = json.loads(report.report_json)
        assert report.scope_type == ReportScopeType.ALL_STORES.value
        assert report.report_kind == ReportKind.DATE_RANGE.value
        assert body["totals"]["ordered_product_sales"] == "300.00"
        assert body["totals"]["units_ordered"] == "15"
        assert len(body["store_summaries"]) == 2


def test_generate_report_fails_without_data(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        try:
            generate_report(
                session=session,
                storage=LocalStorageBackend(tmp_path),
                request=GenerateReportRequest(
                    scope_type=ReportScopeType.ALL_STORES,
                    report_kind=ReportKind.SINGLE_DAY,
                    report_start_date=date(2026, 5, 25),
                    report_end_date=date(2026, 5, 25),
                    data_source="business",
                ),
            )
        except ValueError as exc:
            assert "no business data" in str(exc)
        else:
            raise AssertionError("Expected report generation to fail without data")


def _create_business_row(
    session,
    *,
    display_name: str,
    seller_id: str,
    sales: Decimal,
    units: int,
) -> tuple[SellerAccount, Marketplace]:
    org = session.query(Organization).filter_by(slug="internal").one_or_none()
    if org is None:
        org = Organization(name="Internal Team", slug="internal")
    seller = SellerAccount(
        organization=org,
        display_name=display_name,
        amazon_seller_id=seller_id,
    )
    marketplace = Marketplace(
        seller_account=seller,
        marketplace_id=f"ATVPDKIKX0DER-{seller_id}",
        region="americas",
        country_code="US",
        timezone="America/Los_Angeles",
        currency_code="USD",
    )
    job = ImportJob(
        seller_account=seller,
        marketplace=marketplace,
        source=DataSource.MANUAL_FILE.value,
        report_type=ReportType.BUSINESS_REPORT.value,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        status="succeeded",
        original_filename="business.csv",
    )
    dataset = RawDataset(
        import_job=job,
        seller_account=seller,
        marketplace=marketplace,
        source=DataSource.MANUAL_FILE.value,
        report_type=ReportType.BUSINESS_REPORT.value,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        schema_version="business_report.v1",
        raw_file_path=f"raw/{seller_id}.csv",
        raw_file_checksum=f"checksum-{seller_id}",
        row_count=1,
        data_status="stable",
        data_version=f"business_report:2026-05-25:{seller_id}",
    )
    session.add(
        NormalizedBusinessDaily(
            raw_dataset=dataset,
            seller_account=seller,
            marketplace=marketplace,
            report_date=date(2026, 5, 25),
            asin="B0TESTASIN",
            sku=f"SKU-{seller_id}",
            ordered_product_sales=sales,
            units_ordered=units,
            sessions=100,
            page_views=180,
            conversion_rate=Decimal("0.12"),
            buy_box_percentage=Decimal("0.98"),
        )
    )
    session.flush()
    return seller, marketplace
