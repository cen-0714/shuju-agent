from datetime import date
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.domain.enums import ReportKind, ReportScopeType, ReportStatus, ReportType
from app.models.base import Base
from app.models.imports import ImportJob, RawReportRow
from app.models.normalized import NormalizedBusinessDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.imports.deletion import delete_import_job
from app.services.imports.persistence import confirm_manual_import


def test_delete_import_removes_rows_file_and_marks_reports_stale(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    storage = LocalStorageBackend(tmp_path)
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

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
        session.add(marketplace)
        session.flush()
        import_response = confirm_manual_import(
            session=session,
            storage=storage,
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            report_type=ReportType.BUSINESS_REPORT,
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            original_filename="business_report.csv",
            file_bytes=fixture.read_bytes(),
        )
        report = DailyReport(
            organization=org,
            scope_type=ReportScopeType.SINGLE_STORE.value,
            seller_account=seller,
            marketplace=marketplace,
            report_kind=ReportKind.SINGLE_DAY.value,
            report_date=date(2026, 5, 25),
            report_start_date=date(2026, 5, 25),
            report_end_date=date(2026, 5, 25),
            report_version=1,
            status=ReportStatus.ACTIVE.value,
            data_version="business_report:2026-05-25:test",
            metric_definition_version="v1",
            prompt_version="v1",
            model_name="mock",
            report_json="{}",
            markdown="ok",
            markdown_path="reports/markdown/report.md",
            excel_path="reports/excel/report.xlsx",
            llm_status="skipped",
        )
        session.add(report)
        session.commit()

        assert storage.exists(import_response.raw_file_path)

        delete_import_job(session, storage, import_response.import_job_id)
        session.commit()

        job = session.get(ImportJob, import_response.import_job_id)
        assert job is not None
        assert job.status == "deleted"
        assert job.deleted_at is not None
        assert not storage.exists(import_response.raw_file_path)
        assert session.scalar(select(func.count()).select_from(RawReportRow)) == 0
        assert session.scalar(select(func.count()).select_from(NormalizedBusinessDaily)) == 0
        assert report.status == ReportStatus.STALE.value
