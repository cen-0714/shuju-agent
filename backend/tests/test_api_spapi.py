from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.main import create_app
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount


def test_report_types_endpoint_returns_only_enabled_types() -> None:
    client = TestClient(create_app())

    response = client.get("/api/spapi/report-types")

    assert response.status_code == 200
    payload = response.json()
    internal_types = {item["internal_report_type"] for item in payload}
    assert internal_types == {"business_sales_traffic", "orders_by_date"}
    assert "open_listings" not in response.text


def make_db_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    def override_settings() -> Settings:
        return Settings(
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            AMAZON_LWA_CLIENT_ID="client-id",
            AMAZON_LWA_CLIENT_SECRET="client-secret",
            TOKEN_ENCRYPTION_KEY="MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY=",
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app), session_factory


def seed_store_with_authorization(session: Session) -> tuple[SellerAccount, Marketplace]:
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
    session.add(
        AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="client-id",
            refresh_token_encrypted="encrypted-refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status="active",
        )
    )
    session.flush()
    return seller, marketplace


def test_create_sync_job_uses_enabled_report_type_and_authorization() -> None:
    client, session_factory = make_db_client()
    with session_factory() as session:
        seller, marketplace = seed_store_with_authorization(session)
        session.commit()
        seller_id = seller.id
        marketplace_id = marketplace.id

    response = client.post(
        "/api/spapi/sync-jobs",
        json={
            "seller_account_id": seller_id,
            "marketplace_id": marketplace_id,
            "internal_report_type": "business_sales_traffic",
            "date_range_start": "2026-05-20",
            "date_range_end": "2026-05-20",
            "report_options": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "draft"
    assert payload["amazon_report_type"] == "GET_SALES_AND_TRAFFIC_REPORT"

    with session_factory() as session:
        stored = session.query(SPAPISyncJob).one()
        assert stored.report_options_json == '{"dateGranularity":"DAY","asinGranularity":"SKU"}'


def test_create_sync_job_rejects_disabled_report_type() -> None:
    client, session_factory = make_db_client()
    with session_factory() as session:
        seller, marketplace = seed_store_with_authorization(session)
        session.commit()
        seller_id = seller.id
        marketplace_id = marketplace.id

    response = client.post(
        "/api/spapi/sync-jobs",
        json={
            "seller_account_id": seller_id,
            "marketplace_id": marketplace_id,
            "internal_report_type": "open_listings",
            "date_range_start": "2026-05-20",
            "date_range_end": "2026-05-20",
            "report_options": {},
        },
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]
