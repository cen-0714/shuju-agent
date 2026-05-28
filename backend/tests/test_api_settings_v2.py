from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.core.db import create_session_factory, create_sync_engine
from app.main import create_app
from app.models.base import Base


def make_client() -> TestClient:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def test_store_settings_crud_flow() -> None:
    client = make_client()

    seller_response = client.post(
        "/api/settings/seller-accounts",
        json={"display_name": "Store A", "amazon_seller_id": "SELLER-A"},
    )
    assert seller_response.status_code == 200
    seller = seller_response.json()
    assert seller["display_name"] == "Store A"

    marketplace_response = client.post(
        "/api/settings/marketplaces",
        json={
            "seller_account_id": seller["id"],
            "marketplace_id": "ATVPDKIKX0DER",
            "region": "americas",
            "country_code": "US",
            "timezone": "America/Los_Angeles",
            "currency_code": "USD",
        },
    )
    assert marketplace_response.status_code == 200
    marketplace = marketplace_response.json()
    assert marketplace["country_code"] == "US"

    options_response = client.get("/api/settings/store-options")
    assert options_response.status_code == 200
    options = options_response.json()
    assert options[0]["seller_account_id"] == seller["id"]
    assert options[0]["marketplace_id"] == marketplace["id"]
    assert options[0]["label"] == "Store A - US"


def test_can_disable_marketplace() -> None:
    client = make_client()
    seller = client.post(
        "/api/settings/seller-accounts",
        json={"display_name": "Store B", "amazon_seller_id": "SELLER-B"},
    ).json()
    marketplace = client.post(
        "/api/settings/marketplaces",
        json={
            "seller_account_id": seller["id"],
            "marketplace_id": "A2EUQ1WTGCTBG2",
            "region": "americas",
            "country_code": "CA",
            "timezone": "America/Toronto",
            "currency_code": "CAD",
        },
    ).json()

    response = client.patch(
        f"/api/settings/marketplaces/{marketplace['id']}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False
