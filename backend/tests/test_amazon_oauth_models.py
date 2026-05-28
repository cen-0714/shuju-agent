from datetime import timedelta

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus, AmazonOAuthSessionStatus
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
from app.models.base import Base
from app.models.settings import Organization, SellerAccount


def test_amazon_oauth_settings_defaults() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert settings.PUBLIC_BASE_URL is None
    assert settings.AMAZON_LWA_CLIENT_ID is None
    assert settings.AMAZON_LWA_CLIENT_SECRET is None
    assert settings.AMAZON_LWA_TOKEN_URL == "https://api.amazon.com/auth/o2/token"
    assert settings.AMAZON_OAUTH_LOGIN_PATH == "/api/auth/amazon/login"
    assert settings.AMAZON_OAUTH_REDIRECT_PATH == "/api/auth/amazon/callback"
    assert settings.AMAZON_OAUTH_STATE_TTL_MINUTES == 10
    assert settings.TOKEN_ENCRYPTION_KEY is None


def test_amazon_oauth_models_persist_session_and_authorization() -> None:
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
        oauth_session = AmazonAuthorizationSession(
            state="local-state",
            amazon_state="amazon-state",
            amazon_callback_uri="https://sellercentral.amazon.com/apps/authorize/confirm",
            selling_partner_id="A3FHEXAMPLEYWS",
            status=AmazonOAuthSessionStatus.CREATED.value,
            expires_at=utc_now() + timedelta(minutes=10),
        )
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="amzn1.application-oa2-client.example",
            refresh_token_encrypted="encrypted-refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status=AmazonAuthorizationStatus.ACTIVE.value,
        )

        session.add_all([oauth_session, authorization])
        session.commit()

        assert oauth_session.id is not None
        assert oauth_session.status == "created"
        assert authorization.id is not None
        assert authorization.seller_account_id == seller.id
        assert authorization.refresh_token_encrypted == "encrypted-refresh-token"
