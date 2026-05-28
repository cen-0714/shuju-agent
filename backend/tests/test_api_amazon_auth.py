from collections.abc import Generator
from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import AmazonOAuthSessionStatus
from app.main import create_app
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
from app.models.base import Base
from app.models.settings import Organization, SellerAccount
from app.services.amazon.lwa import LWAClient
from app.services.security.tokens import TokenCipher

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


def make_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        PUBLIC_BASE_URL="https://spapi.example.com",
        AMAZON_LWA_CLIENT_ID="client-id",
        AMAZON_LWA_CLIENT_SECRET="client-secret",
        TOKEN_ENCRYPTION_KEY=TEST_KEY,
    )


def make_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = make_settings
    return TestClient(app), session_factory


def seed_session(
    session_factory: sessionmaker[Session],
    *,
    state: str = "local-state",
    selling_partner_id: str = "A3FHEXAMPLEYWS",
    status: str = AmazonOAuthSessionStatus.CREATED.value,
    expires_delta: timedelta = timedelta(minutes=10),
) -> None:
    with session_factory() as session:
        session.add(
            AmazonAuthorizationSession(
                state=state,
                amazon_state="amazon-state",
                amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
                selling_partner_id=selling_partner_id,
                status=status,
                expires_at=utc_now() + expires_delta,
            )
        )
        session.commit()


def test_status_endpoint_returns_uris_without_secrets() -> None:
    client, _session_factory = make_client()

    response = client.get("/api/auth/amazon/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["login_uri"] == "https://spapi.example.com/api/auth/amazon/login"
    assert payload["redirect_uri"] == "https://spapi.example.com/api/auth/amazon/callback"
    assert payload["lwa_client_secret_configured"] is True
    assert "client-secret" not in response.text
    assert "TOKEN_ENCRYPTION_KEY" not in response.text


def test_login_endpoint_creates_state_and_redirects() -> None:
    client, session_factory = make_client()

    response = client.get(
        "/api/auth/amazon/login",
        params={
            "amazon_callback_uri": "https://sellercentral.amazon.com/apps/authorize/confirm",
            "amazon_state": "amazon-state",
            "selling_partner_id": "A3FHEXAMPLEYWS",
        },
        follow_redirects=False,
    )

    assert response.status_code == 307
    assert response.headers["location"].startswith(
        "https://sellercentral.amazon.com/apps/authorize/confirm?"
    )
    assert "amazon_state=amazon-state" in response.headers["location"]
    with session_factory() as session:
        saved = session.query(AmazonAuthorizationSession).one()
        assert f"state={saved.state}" in response.headers["location"]
        assert saved.selling_partner_id == "A3FHEXAMPLEYWS"


def test_callback_endpoint_saves_encrypted_authorization() -> None:
    client, session_factory = make_client()
    seed_session(session_factory)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "refresh_token": "refresh-token",
                "access_token": "access-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    from app.api.routes import amazon_auth

    def override_lwa_client() -> LWAClient:
        settings = make_settings()
        return LWAClient(
            token_url=settings.AMAZON_LWA_TOKEN_URL,
            client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            client_secret=settings.AMAZON_LWA_CLIENT_SECRET or "",
            transport=httpx.MockTransport(handler),
        )

    client.app.dependency_overrides[amazon_auth.get_lwa_client] = override_lwa_client

    response = client.get(
        "/api/auth/amazon/callback",
        params={
            "state": "local-state",
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "spapi_oauth_code": "spapi-code",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "active"
    cipher = TokenCipher(TEST_KEY)
    with session_factory() as session:
        authorization = session.query(AmazonAuthorization).one()
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"


def test_callback_endpoint_rejects_reused_state() -> None:
    client, session_factory = make_client()
    seed_session(session_factory, status=AmazonOAuthSessionStatus.CONSUMED.value)

    response = client.get(
        "/api/auth/amazon/callback",
        params={
            "state": "local-state",
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "spapi_oauth_code": "spapi-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "state has already been used"


def test_callback_endpoint_rejects_expired_state() -> None:
    client, session_factory = make_client()
    seed_session(session_factory, expires_delta=timedelta(minutes=-1))

    response = client.get(
        "/api/auth/amazon/callback",
        params={
            "state": "local-state",
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "spapi_oauth_code": "spapi-code",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "state expired"


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
