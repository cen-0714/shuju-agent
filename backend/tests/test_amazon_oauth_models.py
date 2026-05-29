from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus
from app.models.amazon import AmazonAuthorization
from app.models.base import Base
from app.models.settings import Organization, SellerAccount


def test_amazon_self_authorization_settings_defaults() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert not hasattr(settings, "PUBLIC_BASE_URL")
    assert settings.AMAZON_LWA_CLIENT_ID is None
    assert settings.AMAZON_LWA_CLIENT_SECRET is None
    assert settings.AMAZON_LWA_TOKEN_URL == "https://api.amazon.com/auth/o2/token"
    assert settings.AMAZON_LWA_TIMEOUT_SECONDS == 15
    assert settings.TOKEN_ENCRYPTION_KEY is None


def test_amazon_authorization_model_persists_without_oauth_session_table() -> None:
    assert "amazon_authorization_sessions" not in Base.metadata.tables

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
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="amzn1.application-oa2-client.example",
            refresh_token_encrypted="encrypted-refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status=AmazonAuthorizationStatus.ACTIVE.value,
        )

        session.add(authorization)
        session.commit()

        assert authorization.id is not None
        assert authorization.seller_account_id == seller.id
        assert authorization.refresh_token_encrypted == "encrypted-refresh-token"
        assert authorization.status == "active"
