from datetime import timedelta

import pytest

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import AmazonOAuthSessionStatus
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
from app.models.base import Base
from app.models.settings import Organization, SellerAccount
from app.services.amazon.lwa import LWATokenExchangeError, LWATokenResponse
from app.services.amazon.oauth import (
    AmazonOAuthError,
    create_login_redirect,
    get_oauth_status,
    handle_authorization_callback,
)
from app.services.security.tokens import TokenCipher

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


class FakeLWAClient:
    def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
        assert code == "spapi-code"
        assert redirect_uri == "https://spapi.example.com/api/auth/amazon/callback"
        return LWATokenResponse(
            refresh_token="refresh-token",
            access_token="access-token",
            token_type="bearer",
            expires_in=3600,
        )


def make_settings() -> Settings:
    return Settings(
        DATABASE_URL="sqlite+pysqlite:///:memory:",
        PUBLIC_BASE_URL="https://spapi.example.com",
        AMAZON_LWA_CLIENT_ID="client-id",
        AMAZON_LWA_CLIENT_SECRET="client-secret",
        TOKEN_ENCRYPTION_KEY=TEST_KEY,
    )


def make_session_factory():
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def test_oauth_status_returns_public_uris_and_config_flags() -> None:
    status = get_oauth_status(make_settings())

    assert status.public_base_url_configured is True
    assert status.lwa_client_id_configured is True
    assert status.lwa_client_secret_configured is True
    assert status.token_encryption_key_configured is True
    assert status.login_uri == "https://spapi.example.com/api/auth/amazon/login"
    assert status.redirect_uri == "https://spapi.example.com/api/auth/amazon/callback"


def test_create_login_redirect_persists_one_time_state() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        result = create_login_redirect(
            session=session,
            settings=make_settings(),
            amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
            amazon_state="amazon-state",
            selling_partner_id="A3FHEXAMPLEYWS",
        )
        session.commit()

        saved = session.query(AmazonAuthorizationSession).one()
        assert saved.state == result.state
        assert saved.amazon_state == "amazon-state"
        assert saved.selling_partner_id == "A3FHEXAMPLEYWS"
        assert saved.status == "created"
        assert result.redirect_url.startswith(
            "https://sellercentral.amazon.com/apps/authorize/confirm?"
        )
        assert f"state={result.state}" in result.redirect_url
        assert "amazon_state=amazon-state" in result.redirect_url


def test_create_login_redirect_rejects_non_https_callback() -> None:
    session_factory = make_session_factory()
    with session_factory() as session:
        with pytest.raises(AmazonOAuthError, match="amazon_callback_uri must use https"):
            create_login_redirect(
                session=session,
                settings=make_settings(),
                amazon_callback_uri="http://sellercentral.amazon.com/apps/authorize/confirm",
                amazon_state="amazon-state",
                selling_partner_id="A3FHEXAMPLEYWS",
            )


def test_handle_callback_saves_encrypted_authorization_and_consumes_session() -> None:
    session_factory = make_session_factory()
    settings = make_settings()
    cipher = TokenCipher(TEST_KEY)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        oauth_session = AmazonAuthorizationSession(
            state="local-state",
            amazon_state="amazon-state",
            amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
            selling_partner_id="A3FHEXAMPLEYWS",
            status=AmazonOAuthSessionStatus.CREATED.value,
            expires_at=utc_now() + timedelta(minutes=10),
        )
        session.add_all([seller, oauth_session])
        session.commit()

        result = handle_authorization_callback(
            session=session,
            settings=settings,
            state="local-state",
            selling_partner_id="A3FHEXAMPLEYWS",
            spapi_oauth_code="spapi-code",
            lwa_client=FakeLWAClient(),
            token_cipher=cipher,
        )
        session.commit()

        authorization = session.query(AmazonAuthorization).one()
        assert result.authorization_id == authorization.id
        assert result.seller_account_id == seller.id
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"
        assert authorization.status == "active"
        assert oauth_session.status == "consumed"
        assert oauth_session.consumed_at is not None


def test_handle_callback_rejects_seller_mismatch() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        oauth_session = AmazonAuthorizationSession(
            state="local-state",
            amazon_state="amazon-state",
            amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
            selling_partner_id="A3FHEXAMPLEYWS",
            status=AmazonOAuthSessionStatus.CREATED.value,
            expires_at=utc_now() + timedelta(minutes=10),
        )
        session.add(oauth_session)
        session.commit()

        with pytest.raises(AmazonOAuthError, match="selling_partner_id does not match"):
            handle_authorization_callback(
                session=session,
                settings=make_settings(),
                state="local-state",
                selling_partner_id="OTHERSELLER",
                spapi_oauth_code="spapi-code",
                lwa_client=FakeLWAClient(),
                token_cipher=TokenCipher(TEST_KEY),
            )


def test_handle_callback_marks_session_failed_when_lwa_fails() -> None:
    class FailingLWAClient:
        def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
            raise LWATokenExchangeError("network failure")

    session_factory = make_session_factory()

    with session_factory() as session:
        oauth_session = AmazonAuthorizationSession(
            state="local-state",
            amazon_state="amazon-state",
            amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
            selling_partner_id="A3FHEXAMPLEYWS",
            status=AmazonOAuthSessionStatus.CREATED.value,
            expires_at=utc_now() + timedelta(minutes=10),
        )
        session.add(oauth_session)
        session.commit()

        with pytest.raises(AmazonOAuthError, match="LWA token exchange failed"):
            handle_authorization_callback(
                session=session,
                settings=make_settings(),
                state="local-state",
                selling_partner_id="A3FHEXAMPLEYWS",
                spapi_oauth_code="spapi-code",
                lwa_client=FailingLWAClient(),
                token_cipher=TokenCipher(TEST_KEY),
            )

        assert oauth_session.status == "failed"
