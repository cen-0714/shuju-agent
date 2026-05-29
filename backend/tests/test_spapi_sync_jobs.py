import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.core.time import utc_now
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.amazon.reports_client import AmazonReportDocument, AmazonReportStatus
from app.services.amazon.sync_jobs import refresh_sync_job, run_sync_job


@dataclass
class FakeAccessToken:
    access_token: str = "access-token"
    token_type: str = "bearer"
    expires_in: int = 3600


class FakeLWAClient:
    def exchange_refresh_token(self, *, refresh_token: str) -> FakeAccessToken:
        assert refresh_token == "refresh-token"
        return FakeAccessToken()


class FakeReportsClient:
    def create_report(self, **kwargs) -> str:
        assert kwargs["access_token"] == "access-token"
        assert kwargs["amazon_report_type"] == "GET_SALES_AND_TRAFFIC_REPORT"
        return "report-1"

    def get_report(self, *, access_token: str, report_id: str) -> AmazonReportStatus:
        assert access_token == "access-token"
        assert report_id == "report-1"
        return AmazonReportStatus(
            report_id="report-1",
            processing_status="DONE",
            report_document_id="document-1",
        )

    def get_report_document(
        self,
        *,
        access_token: str,
        report_document_id: str,
    ) -> AmazonReportDocument:
        assert access_token == "access-token"
        assert report_document_id == "document-1"
        return AmazonReportDocument(
            report_document_id="document-1",
            url="https://download.example.test/document-1",
            compression_algorithm=None,
        )


def test_run_and_refresh_sync_job_imports_downloaded_report(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    content = (Path(__file__).parent / "fixtures" / "sales_and_traffic_report.json").read_bytes()

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="client-id",
            refresh_token_encrypted="refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status="active",
        )
        sync_job = SPAPISyncJob(
            seller_account=seller,
            marketplace=marketplace,
            amazon_authorization=authorization,
            internal_report_type="business_sales_traffic",
            amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
            date_range_start=date(2026, 5, 20),
            date_range_end=date(2026, 5, 20),
            report_options_json=json.dumps(
                {"dateGranularity": "DAY", "asinGranularity": "SKU"}
            ),
            status="draft",
        )
        session.add(sync_job)
        session.flush()

        run_sync_job(
            session=session,
            sync_job_id=sync_job.id,
            refresh_token_plaintext="refresh-token",
            lwa_client=FakeLWAClient(),
            reports_client=FakeReportsClient(),
        )
        assert sync_job.status == "requested"
        assert sync_job.amazon_report_id == "report-1"

        refresh_sync_job(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            sync_job_id=sync_job.id,
            refresh_token_plaintext="refresh-token",
            lwa_client=FakeLWAClient(),
            reports_client=FakeReportsClient(),
            downloaded_content=content,
        )
        assert sync_job.status == "imported"
        assert sync_job.import_job_id is not None
        assert sync_job.amazon_report_document_id == "document-1"
