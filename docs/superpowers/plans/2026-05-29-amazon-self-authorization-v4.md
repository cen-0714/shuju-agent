# Amazon Self Authorization V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the V3 Website OAuth callback path with an internal self-authorization flow where the user manually enters Amazon refresh tokens generated in Amazon's developer portal.

**Architecture:** Keep the existing FastAPI monolith and reuse the `amazon_authorizations` table plus Fernet token encryption. Remove public Login/Callback endpoints, remove OAuth state-session persistence, and add a self-authorization service/API/page surface that stores refresh tokens without ever returning plaintext or encrypted token values.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, SQLite for tests, Jinja2, cryptography Fernet, pytest, ruff.

---

## Scope Check

This plan implements `docs/superpowers/specs/2026-05-29-amazon-self-authorization-v4-design.md`.

V4 includes:

- `POST /api/auth/amazon/self-authorizations`
- `GET /api/auth/amazon/authorizations`
- `DELETE /api/auth/amazon/authorizations/{authorization_id}`
- `GET /api/auth/amazon/status`
- Settings page copy and fields for internal Amazon self-authorization.
- Removal of Website OAuth Login/Callback endpoints.
- Removal of OAuth state-session model and table.
- README update for internal self-authorization.

V4 excludes:

- External seller authorization.
- SaaS authorization compatibility.
- `PUBLIC_BASE_URL`, Login URI, Redirect URI, Cloudflare Tunnel as required configuration.
- SP-API Reports/Orders/Inventory calls.
- Amazon Ads API.
- Token rotation and Amazon-side revocation checks.

## File Structure

Create, modify, or delete these files:

```text
backend/app/core/config.py
backend/app/domain/enums.py
backend/app/models/amazon.py
backend/app/models/__init__.py
backend/app/schemas/amazon.py
backend/app/api/routes/amazon_auth.py
backend/app/services/amazon/authorization.py
backend/app/services/amazon/oauth.py
backend/app/web/templates/settings.html
backend/migrations/versions/20260529_0004_self_authorization.py
backend/tests/test_amazon_authorization_service.py
backend/tests/test_api_amazon_auth.py
backend/tests/test_amazon_oauth_models.py
backend/tests/test_amazon_oauth_service.py
backend/tests/test_web_v2.py
README.md
```

Responsibilities:

- `core/config.py`: remove Website OAuth configuration; keep LWA and token encryption configuration.
- `domain/enums.py`: remove `AmazonOAuthSessionStatus`; keep `AmazonAuthorizationStatus`.
- `models/amazon.py`: remove `AmazonAuthorizationSession`; keep `AmazonAuthorization`.
- `schemas/amazon.py`: define self-authorization request, safe authorization response, and internal config status response.
- `services/amazon/authorization.py`: save, upsert, list, and delete self-authorized refresh tokens.
- `api/routes/amazon_auth.py`: expose V4 internal auth endpoints only.
- `services/amazon/oauth.py`: delete this file after moving the useful authorization logic into `authorization.py`.
- `settings.html`: add internal self-authorization section.
- `20260529_0004_self_authorization.py`: drop `amazon_authorization_sessions` table.
- Tests: replace Website OAuth tests with self-authorization tests.
- `README.md`: remove Login/Callback and public-domain instructions; document internal self-authorization.

## Task 1: Replace OAuth Models and Config

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/app/models/amazon.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/test_amazon_oauth_models.py`
- Create: `backend/migrations/versions/20260529_0004_self_authorization.py`

- [ ] **Step 1: Rewrite model/config tests for V4**

Replace `backend/tests/test_amazon_oauth_models.py` with:

```python
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
```

- [ ] **Step 2: Run model/config tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py -q
```

Expected: FAIL because `Settings` still contains Website OAuth fields and `Base.metadata` still includes `amazon_authorization_sessions`.

- [ ] **Step 3: Remove Website OAuth config**

Modify `backend/app/core/config.py` to remove:

```python
PUBLIC_BASE_URL: str | None = None
AMAZON_OAUTH_LOGIN_PATH: str = "/api/auth/amazon/login"
AMAZON_OAUTH_REDIRECT_PATH: str = "/api/auth/amazon/callback"
AMAZON_OAUTH_STATE_TTL_MINUTES: int = 10
```

Keep:

```python
AMAZON_LWA_CLIENT_ID: str | None = None
AMAZON_LWA_CLIENT_SECRET: str | None = None
AMAZON_LWA_TOKEN_URL: str = "https://api.amazon.com/auth/o2/token"
AMAZON_LWA_TIMEOUT_SECONDS: int = 15
TOKEN_ENCRYPTION_KEY: str | None = None
```

- [ ] **Step 4: Remove OAuth session enum and model**

Modify `backend/app/domain/enums.py` by deleting:

```python
class AmazonOAuthSessionStatus(StrEnum):
    CREATED = "created"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    FAILED = "failed"
```

Modify `backend/app/models/amazon.py` so the complete file is:

```python
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.settings import SellerAccount


class AmazonAuthorization(TimestampMixin, Base):
    __tablename__ = "amazon_authorizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    selling_partner_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    seller_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("seller_accounts.id"), nullable=True, index=True
    )
    lwa_client_id: Mapped[str] = mapped_column(String(255))
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    token_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    seller_account: Mapped["SellerAccount | None"] = relationship()
```

Modify `backend/app/models/__init__.py` to remove `AmazonAuthorizationSession` from imports and `__all__`.

- [ ] **Step 5: Add migration to drop OAuth sessions**

Create `backend/migrations/versions/20260529_0004_self_authorization.py`:

```python
"""drop amazon oauth sessions

Revision ID: 20260529_0004
Revises: 20260528_0003
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_expires_at"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_status"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_selling_partner_id"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_index(
        op.f("ix_amazon_authorization_sessions_state"),
        table_name="amazon_authorization_sessions",
    )
    op.drop_table("amazon_authorization_sessions")


def downgrade() -> None:
    op.create_table(
        "amazon_authorization_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=160), nullable=False),
        sa.Column("amazon_state", sa.String(length=500), nullable=False),
        sa.Column("amazon_callback_uri", sa.Text(), nullable=False),
        sa.Column("selling_partner_id", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_amazon_authorization_sessions")),
        sa.UniqueConstraint("state", name=op.f("uq_amazon_authorization_sessions_state")),
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_state"),
        "amazon_authorization_sessions",
        ["state"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_selling_partner_id"),
        "amazon_authorization_sessions",
        ["selling_partner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_status"),
        "amazon_authorization_sessions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorization_sessions_expires_at"),
        "amazon_authorization_sessions",
        ["expires_at"],
        unique=False,
    )
```

- [ ] **Step 6: Run model/config tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add backend/app/core/config.py backend/app/domain/enums.py backend/app/models/amazon.py backend/app/models/__init__.py backend/migrations/versions/20260529_0004_self_authorization.py backend/tests/test_amazon_oauth_models.py
git commit -m "feat: remove website oauth session model"
```

## Task 2: Add Self-Authorization Service

**Files:**
- Create: `backend/app/services/amazon/authorization.py`
- Delete: `backend/app/services/amazon/oauth.py`
- Create: `backend/tests/test_amazon_authorization_service.py`
- Delete: `backend/tests/test_amazon_oauth_service.py`

- [ ] **Step 1: Write self-authorization service tests**

Create `backend/tests/test_amazon_authorization_service.py`:

```python
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


def test_authorization_status_reports_internal_config_only() -> None:
    status = get_authorization_status(make_settings())

    assert status.lwa_client_id_configured is True
    assert status.lwa_client_secret_configured is True
    assert status.token_encryption_key_configured is True
    assert status.token_url == "https://api.amazon.com/auth/o2/token"
    assert not hasattr(status, "login_uri")
    assert not hasattr(status, "redirect_uri")


def test_save_self_authorization_encrypts_token_and_binds_seller() -> None:
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

        result = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="refresh-token",
            token_type="bearer",
        )
        session.commit()

        authorization = session.get(AmazonAuthorization, result.id)
        assert authorization is not None
        assert authorization.seller_account_id == seller.id
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"
        assert authorization.status == "active"


def test_save_self_authorization_allows_unbound_seller() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        result = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="UNBOUNDSELLER",
            refresh_token="refresh-token",
            token_type="bearer",
        )
        session.commit()

        authorization = session.get(AmazonAuthorization, result.id)
        assert authorization is not None
        assert authorization.seller_account_id is None


def test_save_self_authorization_upserts_by_selling_partner_id() -> None:
    session_factory = make_session_factory()
    cipher = TokenCipher(TEST_KEY)

    with session_factory() as session:
        first = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="old-token",
            token_type="bearer",
        )
        second = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="new-token",
            token_type="bearer",
        )
        session.commit()

        authorizations = session.query(AmazonAuthorization).all()
        assert len(authorizations) == 1
        assert first.id == second.id
        assert cipher.decrypt(authorizations[0].refresh_token_encrypted) == "new-token"


def test_save_self_authorization_requires_lwa_client_id() -> None:
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
        saved = save_self_authorization(
            session=session,
            settings=make_settings(),
            selling_partner_id="A3FHEXAMPLEYWS",
            refresh_token="refresh-token",
            token_type="bearer",
        )
        delete_authorization(session, saved.id)
        session.commit()

        assert session.get(AmazonAuthorization, saved.id) is None


def test_delete_authorization_raises_for_missing_record() -> None:
    session_factory = make_session_factory()

    with session_factory() as session:
        with pytest.raises(AmazonAuthorizationNotFoundError):
            delete_authorization(session, 999)
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_authorization_service.py -q
```

Expected: FAIL because `app.services.amazon.authorization` does not exist yet.

- [ ] **Step 3: Implement self-authorization service**

Create `backend/app/services/amazon/authorization.py`:

```python
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus
from app.models.amazon import AmazonAuthorization
from app.models.settings import SellerAccount
from app.services.security.tokens import TokenCipher, TokenCipherConfigError


class AmazonAuthorizationConfigError(ValueError):
    pass


class AmazonAuthorizationNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class AmazonAuthorizationStatusSummary:
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    token_url: str


def get_authorization_status(settings: Settings) -> AmazonAuthorizationStatusSummary:
    return AmazonAuthorizationStatusSummary(
        lwa_client_id_configured=bool(settings.AMAZON_LWA_CLIENT_ID),
        lwa_client_secret_configured=bool(settings.AMAZON_LWA_CLIENT_SECRET),
        token_encryption_key_configured=bool(settings.TOKEN_ENCRYPTION_KEY),
        token_url=settings.AMAZON_LWA_TOKEN_URL,
    )


def save_self_authorization(
    *,
    session: Session,
    settings: Settings,
    selling_partner_id: str,
    refresh_token: str,
    token_type: str | None,
) -> AmazonAuthorization:
    if not settings.AMAZON_LWA_CLIENT_ID:
        raise AmazonAuthorizationConfigError("AMAZON_LWA_CLIENT_ID is required")

    try:
        cipher = TokenCipher(settings.TOKEN_ENCRYPTION_KEY)
    except TokenCipherConfigError as exc:
        raise AmazonAuthorizationConfigError(str(exc)) from exc

    seller_account = session.scalar(
        select(SellerAccount).where(SellerAccount.amazon_seller_id == selling_partner_id)
    )
    authorization = session.scalar(
        select(AmazonAuthorization).where(
            AmazonAuthorization.selling_partner_id == selling_partner_id
        )
    )
    encrypted_token = cipher.encrypt(refresh_token)
    now = utc_now()

    if authorization is None:
        authorization = AmazonAuthorization(
            selling_partner_id=selling_partner_id,
            seller_account=seller_account,
            lwa_client_id=settings.AMAZON_LWA_CLIENT_ID,
            refresh_token_encrypted=encrypted_token,
            token_type=token_type,
            authorized_at=now,
            status=AmazonAuthorizationStatus.ACTIVE.value,
        )
        session.add(authorization)
    else:
        authorization.seller_account = seller_account
        authorization.lwa_client_id = settings.AMAZON_LWA_CLIENT_ID
        authorization.refresh_token_encrypted = encrypted_token
        authorization.token_type = token_type
        authorization.authorized_at = now
        authorization.status = AmazonAuthorizationStatus.ACTIVE.value
        authorization.last_error = None

    session.flush()
    return authorization


def delete_authorization(session: Session, authorization_id: int) -> None:
    authorization = session.get(AmazonAuthorization, authorization_id)
    if authorization is None:
        raise AmazonAuthorizationNotFoundError("authorization not found")
    session.delete(authorization)
    session.flush()
```

Delete `backend/app/services/amazon/oauth.py`.

- [ ] **Step 4: Run service tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_authorization_service.py -q
```

Expected: PASS.

- [ ] **Step 5: Delete old OAuth service tests**

Delete `backend/tests/test_amazon_oauth_service.py`.

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_authorization_service.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add backend/app/services/amazon/authorization.py backend/app/services/amazon/oauth.py backend/tests/test_amazon_authorization_service.py backend/tests/test_amazon_oauth_service.py
git commit -m "feat: add amazon self authorization service"
```

## Task 3: Replace Amazon Auth API Routes

**Files:**
- Modify: `backend/app/schemas/amazon.py`
- Modify: `backend/app/api/routes/amazon_auth.py`
- Modify: `backend/tests/test_api_amazon_auth.py`

- [ ] **Step 1: Rewrite API tests for V4**

Replace `backend/tests/test_api_amazon_auth.py` with:

```python
from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.models.amazon import AmazonAuthorization
from app.models.base import Base
from app.models.settings import Organization, SellerAccount
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


def make_client(settings_factory=make_settings) -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    from app.main import create_app

    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = settings_factory
    return TestClient(app), session_factory


def test_status_endpoint_returns_internal_config_only() -> None:
    client, _session_factory = make_client()

    response = client.get("/api/auth/amazon/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "lwa_client_id_configured": True,
        "lwa_client_secret_configured": True,
        "token_encryption_key_configured": True,
        "token_url": "https://api.amazon.com/auth/o2/token",
    }
    assert "login_uri" not in response.text
    assert "redirect_uri" not in response.text
    assert "client-secret" not in response.text
    assert TEST_KEY not in response.text


def test_website_oauth_routes_are_removed() -> None:
    client, _session_factory = make_client()

    assert client.get("/api/auth/amazon/login").status_code == 404
    assert client.get("/api/auth/amazon/callback").status_code == 404


def test_self_authorization_endpoint_saves_encrypted_token_and_binds_seller() -> None:
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
    assert payload["seller_account_id"] is not None
    assert payload["status"] == "active"
    assert "refresh-token" not in response.text
    assert "refresh_token_encrypted" not in response.text

    cipher = TokenCipher(TEST_KEY)
    with session_factory() as session:
        authorization = session.query(AmazonAuthorization).one()
        assert authorization.refresh_token_encrypted != "refresh-token"
        assert cipher.decrypt(authorization.refresh_token_encrypted) == "refresh-token"


def test_self_authorization_endpoint_allows_unbound_seller() -> None:
    client, _session_factory = make_client()

    response = client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "UNBOUNDSELLER",
            "refresh_token": "refresh-token",
        },
    )

    assert response.status_code == 200
    assert response.json()["seller_account_id"] is None


def test_self_authorization_endpoint_reports_missing_encryption_config() -> None:
    client, _session_factory = make_client(
        settings_factory=lambda: make_settings(TOKEN_ENCRYPTION_KEY=None)
    )

    response = client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "refresh_token": "refresh-token",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "TOKEN_ENCRYPTION_KEY is required"


def test_authorizations_endpoint_does_not_return_refresh_token() -> None:
    client, _session_factory = make_client()
    client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "refresh_token": "refresh-token",
        },
    )

    response = client.get("/api/auth/amazon/authorizations")

    assert response.status_code == 200
    assert response.json()[0]["selling_partner_id"] == "A3FHEXAMPLEYWS"
    assert "refresh-token" not in response.text
    assert "refresh_token_encrypted" not in response.text


def test_delete_authorization_endpoint_removes_record() -> None:
    client, _session_factory = make_client()
    created = client.post(
        "/api/auth/amazon/self-authorizations",
        json={
            "selling_partner_id": "A3FHEXAMPLEYWS",
            "refresh_token": "refresh-token",
        },
    ).json()

    response = client.delete(f"/api/auth/amazon/authorizations/{created['id']}")

    assert response.status_code == 204
    assert client.get("/api/auth/amazon/authorizations").json() == []


def test_delete_authorization_endpoint_returns_404_for_missing_record() -> None:
    client, _session_factory = make_client()

    response = client.delete("/api/auth/amazon/authorizations/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "authorization not found"
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_api_amazon_auth.py -q
```

Expected: FAIL because old `/login` and `/callback` still exist and `/self-authorizations` does not exist.

- [ ] **Step 3: Replace schemas**

Modify `backend/app/schemas/amazon.py` so the complete file is:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AmazonAuthorizationStatusResponse(BaseModel):
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    token_url: str


class AmazonSelfAuthorizationCreate(BaseModel):
    selling_partner_id: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    token_type: str | None = "bearer"


class AmazonAuthorizationResponse(BaseModel):
    id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str
    authorized_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Replace API router**

Modify `backend/app/api/routes/amazon_auth.py` so the complete file is:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.models.amazon import AmazonAuthorization
from app.schemas.amazon import (
    AmazonAuthorizationResponse,
    AmazonAuthorizationStatusResponse,
    AmazonSelfAuthorizationCreate,
)
from app.services.amazon.authorization import (
    AmazonAuthorizationConfigError,
    AmazonAuthorizationNotFoundError,
    delete_authorization,
    get_authorization_status,
    save_self_authorization,
)

router = APIRouter(prefix="/auth/amazon", tags=["amazon-auth"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/status", response_model=AmazonAuthorizationStatusResponse)
def status(settings: SettingsDep) -> AmazonAuthorizationStatusResponse:
    return AmazonAuthorizationStatusResponse.model_validate(
        get_authorization_status(settings).__dict__
    )


@router.post("/self-authorizations", response_model=AmazonAuthorizationResponse)
def post_self_authorization(
    payload: AmazonSelfAuthorizationCreate,
    session: SessionDep,
    settings: SettingsDep,
) -> AmazonAuthorization:
    try:
        authorization = save_self_authorization(
            session=session,
            settings=settings,
            selling_partner_id=payload.selling_partner_id,
            refresh_token=payload.refresh_token,
            token_type=payload.token_type,
        )
    except AmazonAuthorizationConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    session.commit()
    return authorization


@router.get("/authorizations", response_model=list[AmazonAuthorizationResponse])
def authorizations(session: SessionDep) -> list[AmazonAuthorization]:
    return list(session.scalars(select(AmazonAuthorization).order_by(AmazonAuthorization.id)))


@router.delete("/authorizations/{authorization_id}", status_code=204)
def delete_authorization_endpoint(authorization_id: int, session: SessionDep) -> Response:
    try:
        delete_authorization(session, authorization_id)
    except AmazonAuthorizationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    return Response(status_code=204)
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_amazon_auth.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add backend/app/schemas/amazon.py backend/app/api/routes/amazon_auth.py backend/tests/test_api_amazon_auth.py
git commit -m "feat: replace amazon oauth routes with self authorization"
```

## Task 4: Settings Page and README

**Files:**
- Modify: `backend/app/web/templates/settings.html`
- Modify: `backend/tests/test_web_v2.py`
- Modify: `README.md`

- [ ] **Step 1: Update Settings page test**

Modify the `/settings` expectations in `backend/tests/test_web_v2.py`:

```python
"/settings": [
    "Seller Accounts",
    "Marketplaces",
    "Amazon Self Authorization",
    "Refresh token",
    "LLM Settings",
],
```

- [ ] **Step 2: Run web test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v2.py -q
```

Expected: FAIL because the Settings page does not contain the self-authorization section yet.

- [ ] **Step 3: Add Settings page self-authorization section**

Modify `backend/app/web/templates/settings.html` by adding this section before `LLM Settings`:

```html
<section>
  <h2>Amazon Self Authorization</h2>
  <form method="post" action="/api/auth/amazon/self-authorizations">
    <label>Selling partner ID <input name="selling_partner_id"></label>
    <label>Refresh token <input name="refresh_token" type="password"></label>
    <label>Token type <input name="token_type" value="bearer"></label>
    <button type="submit">Save Amazon Authorization</button>
  </form>
  <p>Refresh tokens are sensitive. Do not commit them, screenshot them, or share them in chat.</p>
</section>
```

- [ ] **Step 4: Update README**

Modify `README.md`:

- Replace “Amazon SP-API 授权：提供 Website OAuth Login URI / Redirect URI” with “Amazon SP-API 自授权：支持录入 Amazon 后台生成的 refresh token，并加密保存”.
- Remove `PUBLIC_BASE_URL`, `AMAZON_OAUTH_LOGIN_PATH`, `AMAZON_OAUTH_REDIRECT_PATH`, and `AMAZON_OAUTH_STATE_TTL_MINUTES` from the configuration block.
- Remove Login URI / Redirect URI instructions.
- Remove Cloudflare Tunnel and public reverse proxy requirements.
- Add self-authorization flow:

````markdown
## Amazon SP-API 自授权配置

V4 使用内部自授权流程，不做 SaaS，不做外部卖家点击授权。

在 Amazon 后台点击“授权应用”生成 refresh token，然后在系统内部保存授权。

`backend\.env` 需要：

```env
AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_LWA_TIMEOUT_SECONDS=15
TOKEN_ENCRYPTION_KEY=
```

保存自授权 token：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/auth/amazon/self-authorizations `
  -ContentType "application/json" `
  -Body '{"selling_partner_id":"A3FHEXAMPLEYWS","refresh_token":"Atzr|example","token_type":"bearer"}'
```

不要使用真实 token 写入 README、Git、聊天或截图。真实 token 泄露后，应在 Amazon 后台重新生成并撤销旧授权。
````

- [ ] **Step 5: Run docs/page tests**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v2.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

Run:

```powershell
git add README.md backend/app/web/templates/settings.html backend/tests/test_web_v2.py
git commit -m "docs: document amazon self authorization"
```

## Task 5: Full Verification and Push

**Files:**
- No additional file edits unless verification finds an issue.

- [ ] **Step 1: Run focused V4 tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py tests/test_amazon_authorization_service.py tests/test_api_amazon_auth.py tests/test_web_v2.py -q
```

Expected: PASS.

- [ ] **Step 2: Run all tests**

Run:

```powershell
cd backend
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run lint**

Run:

```powershell
cd backend
python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 4: Run migration**

With Docker Postgres available:

```powershell
cd backend
python -m alembic upgrade head
python -m alembic current
```

Expected: current revision is `20260529_0004 (head)`.

- [ ] **Step 5: Check removed routes manually**

Run:

```powershell
cd backend
python -m pytest tests/test_api_amazon_auth.py::test_website_oauth_routes_are_removed -q
```

Expected: PASS.

- [ ] **Step 6: Commit any verification fixes**

If verification required edits, commit them:

```powershell
git status --short
git add path\to\changed-file
git commit -m "fix: complete amazon self authorization migration"
```

Replace `path\to\changed-file` with the exact files shown by `git status --short`. If no files changed, skip this step.

- [ ] **Step 7: Report final local status**

Run:

```powershell
git status --short --branch
git log --oneline -8
```

Expected: clean except existing untracked `.claude/`; branch is ahead of origin until user chooses to push.
