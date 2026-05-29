from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.main import create_app
from app.models.amazon import AmazonAuthorization
from app.models.base import Base
from app.models.settings import Organization, SellerAccount
from app.services.security.tokens import TokenCipher

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


def make_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        AMAZON_LWA_CLIENT_ID="client-id",
        AMAZON_LWA_CLIENT_SECRET="client-secret",
        TOKEN_ENCRYPTION_KEY=TEST_KEY,
    )


def make_incomplete_settings() -> Settings:
    return Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")


def make_client(settings_factory=make_settings) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = settings_factory
    return TestClient(app), session_factory


def test_status_endpoint_returns_internal_config_flags_without_secrets() -> None:
    client, _session_factory = make_client()

    response = client.get("/api/auth/amazon/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "lwa_client_id_configured": True,
        "lwa_client_secret_configured": True,
        "token_encryption_key_configured": True,
    }
    assert "client-secret" not in response.text
    assert "TOKEN_ENCRYPTION_KEY" not in response.text
    assert "login_uri" not in payload
    assert "redirect_uri" not in payload


def test_website_oauth_routes_are_removed() -> None:
    client, _session_factory = make_client()

    assert client.get("/api/auth/amazon/login").status_code == 404
    assert client.get("/api/auth/amazon/callback").status_code == 404


def test_self_authorization_endpoint_saves_encrypted_authorization() -> None:
    client, session_factory = make_client()
    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        session.add(seller)
        session.commit()

    response = client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["selling_partner_id"] == "A3FHEXAMPLEYWS"
    assert payload["status"] == "active"
    assert "refresh-token" not in response.text
    assert "refresh_token_encrypted" not in response.text

    cipher = TokenCipher(TEST_KEY)
    with session_factory() as session:
        authorization = session.query(AmazonAuthorization).one()
        assert authorization.seller_account_id == seller.id
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"


def test_self_authorization_endpoint_returns_500_when_config_missing() -> None:
    client, _session_factory = make_client(settings_factory=make_incomplete_settings)

    response = client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
        },
    )

    assert response.status_code == 500
    assert "Missing Amazon authorization config" in response.json()["detail"]


def test_authorizations_endpoint_does_not_return_refresh_token() -> None:
    client, session_factory = make_client()
    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
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
        session.commit()

    response = client.get("/api/auth/amazon/authorizations")

    assert response.status_code == 200
    assert response.json()[0]["selling_partner_id"] == "A3FHEXAMPLEYWS"
    assert "refresh_token" not in response.text
    assert "encrypted-refresh-token" not in response.text


def test_delete_authorization_endpoint_removes_record() -> None:
    client, session_factory = make_client()
    with session_factory() as session:
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            lwa_client_id="client-id",
            refresh_token_encrypted="encrypted-refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status="active",
        )
        session.add(authorization)
        session.commit()
        authorization_id = authorization.id

    response = client.delete(f"/api/auth/amazon/authorizations/{authorization_id}")

    assert response.status_code == 204
    assert response.content == b""
    with session_factory() as session:
        assert session.get(AmazonAuthorization, authorization_id) is None


def test_delete_authorization_endpoint_returns_404_for_missing_record() -> None:
    client, _session_factory = make_client()

    response = client.delete("/api/auth/amazon/authorizations/404")

    assert response.status_code == 404
    assert response.json()["detail"] == "Amazon authorization not found"
