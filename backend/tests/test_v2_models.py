from datetime import date

from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import ImportJobStatus, ReportKind, ReportScopeType, ReportStatus
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset, RawReportRow
from app.models.normalized import NormalizedBusinessDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, Organization, SellerAccount


def test_v2_enums_have_required_values() -> None:
    assert ImportJobStatus.PREVIEWED.value == "previewed"
    assert ImportJobStatus.DELETED.value == "deleted"
    assert ReportScopeType.ALL_STORES.value == "all_stores"
    assert ReportScopeType.SINGLE_STORE.value == "single_store"
    assert ReportKind.SINGLE_DAY.value == "single_day"
    assert ReportKind.DATE_RANGE.value == "date_range"
    assert ReportStatus.ACTIVE.value == "active"
    assert ReportStatus.STALE.value == "stale"


def test_v2_models_can_persist_import_and_report_scope() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="Store A",
            amazon_seller_id="SELLER-A",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        job = ImportJob(
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 27),
            date_range_end=date(2026, 5, 27),
            status="succeeded",
            original_filename="business.csv",
        )
        dataset = RawDataset(
            import_job=job,
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 27),
            date_range_end=date(2026, 5, 27),
            schema_version="business_report.v1",
            raw_file_path="backend/storage/raw/business.csv",
            raw_file_checksum="abc123",
            row_count=1,
            data_status="stable",
            data_version="business_report:2026-05-27:abc123",
        )
        raw_row = RawReportRow(raw_dataset=dataset, row_number=1, row_json='{"Date":"2026-05-27"}')
        normalized = NormalizedBusinessDaily(
            raw_dataset=dataset,
            seller_account=seller,
            marketplace=marketplace,
            report_date=date(2026, 5, 27),
            asin=None,
            sku=None,
            ordered_product_sales=100,
            units_ordered=4,
            sessions=40,
            page_views=80,
            conversion_rate=None,
            buy_box_percentage=None,
        )
        report = DailyReport(
            organization=org,
            scope_type="single_store",
            seller_account=seller,
            marketplace=marketplace,
            report_kind="single_day",
            report_start_date=date(2026, 5, 27),
            report_end_date=date(2026, 5, 27),
            report_version=1,
            status="active",
            data_version="business_report:2026-05-27:abc123",
            metric_definition_version="v1",
            prompt_version="v1",
            model_name="mock",
            report_json="{}",
            markdown="ok",
            markdown_path="backend/storage/reports/markdown/report.md",
            excel_path="backend/storage/reports/excel/report.xlsx",
            llm_status="skipped",
        )
        session.add_all([raw_row, normalized, report])
        session.commit()

        assert dataset.raw_rows[0].row_number == 1
        assert report.scope_type == "single_store"
        assert report.report_start_date == date(2026, 5, 27)
