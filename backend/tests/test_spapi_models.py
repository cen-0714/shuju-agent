from datetime import date

from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import SPAPISyncJobStatus
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount


def test_spapi_sync_job_model_persists_report_lifecycle_fields() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

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
            refresh_token_encrypted="encrypted",
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
            report_options_json='{"dateGranularity":"DAY","asinGranularity":"SKU"}',
            status=SPAPISyncJobStatus.DRAFT.value,
        )
        session.add(sync_job)
        session.commit()

        stored = session.get(SPAPISyncJob, sync_job.id)
        assert stored is not None
        assert stored.seller_account_id == seller.id
        assert stored.marketplace_id == marketplace.id
        assert stored.amazon_authorization_id == authorization.id
        assert stored.import_job_id is None
        assert stored.status == "draft"
        assert stored.amazon_report_id is None
