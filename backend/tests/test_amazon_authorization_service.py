import pytest

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.models.amazon import AmazonAuthorization
from app.models.base import Base
from app.models.settings import Organization, SellerAccount
from app.services.amazon.authorization import (
    AmazonAuthorizationConfigError,
    AmazonAuthorizationNotFoundError,
    delete_authorization,
    get_authorization_status,
    save_self_authorization,
)
from app.services.security.tokens import TokenCipher

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


def make_settings(**overrides: object) -> Settings:
    values = {
        "DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "AMAZON_LWA_CLIENT_ID": "client-id",
        "AMAZON_LWA_CLIENT_SECRET": "client-secret",
        "TOKEN_ENCRYPTION_KEY": TEST_KEY,
    }
    values.update(overrides)
    return Settings(**values)


def make_session_factory():
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def test_authorization_status_returns_internal_config_flags_only() -> None:
    status = get_authorization_status(make_settings())

    assert status.lwa_client_id_configured is True
    assert status.lwa_client_secret_configured is True
    assert status.token_encryption_key_configured is True


def test_save_self_authorization_encrypts_refresh_token_and_links_seller() -> None:
    session_factory = make_session_factory()
    cipher = TokenCipher(TEST_KEY)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        session.add(seller)
        session.commit()

        authorization = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="refresh-token",
            token_type="bearer",
        )
        session.commit()

        assert authorization.id is not None
        assert authorization.seller_account_id == seller.id
        assert authorization.lwa_client_id == "client-id"
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"
        assert authorization.token_type == "bearer"
        assert authorization.status == "active"
        assert authorization.last_error is None


def test_save_self_authorization_updates_existing_authorization() -> None:
    session_factory = make_session_factory()
    cipher = TokenCipher(TEST_KEY)

    with session_factory() as session:
        first = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="old-refresh-token",
            token_type="bearer",
        )
        session.commit()
        first_id = first.id

        updated = save_self_authorization(
            session=session,
            settings=make_settings(AMAZON_LWA_CLIENT_ID="client-id-2"),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="new-refresh-token",
            token_type=None,
        )
        session.commit()

        authorizations = session.query(AmazonAuthorization).all()
        assert len(authorizations) == 1
        assert updated.id == first_id
        assert updated.lwa_client_id == "client-id-2"
        assert cipher.decrypt(updated.refresh_token_encrypted) == "new-refresh-token"
        assert updated.token_type == "bearer"


def test_save_self_authorization_requires_internal_config() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        with pytest.raises(AmazonAuthorizationConfigError, match="AMAZON_LWA_CLIENT_ID"):
            save_self_authorization(
                session=session,
                settings=make_settings(AMAZON_LWA_CLIENT_ID=None),
                selling_partner_id="A3FHEXAMPLEYWS",
                refresh_token="refresh-token",
                token_type="bearer",
            )


def test_delete_authorization_removes_record() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        authorization = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="refresh-token",
            token_type="bearer",
        )
        session.commit()
        authorization_id = authorization.id

        delete_authorization(session, authorization_id)
        session.commit()

        assert session.get(AmazonAuthorization, authorization_id) is None


def test_delete_authorization_raises_for_missing_record() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        with pytest.raises(
            AmazonAuthorizationNotFoundError,
            match="Amazon authorization not found",
        ):
            delete_authorization(session, 404)
