# Amazon SP-API OAuth V3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the V3 Amazon SP-API Website OAuth authorization layer so Amazon can call public Login/Redirect URIs and the app can securely store seller refresh tokens.

**Architecture:** Extend the existing FastAPI monolith with a focused `amazon_auth` API router, SQLAlchemy models for one-time OAuth sessions and seller authorizations, a small LWA token exchange client, and a Fernet token encryption service. V3 stores authorization credentials only; it does not call SP-API reports, orders, inventory, or Ads APIs.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, SQLite for tests, PostgreSQL for local Docker, httpx, cryptography Fernet, pytest, ruff.

---

## Scope Check

This plan implements `docs/superpowers/specs/2026-05-28-amazon-spapi-oauth-v3-design.md`.

V3 includes:

- Public Amazon OAuth Login URI: `GET /api/auth/amazon/login`.
- Public Amazon OAuth Redirect URI: `GET /api/auth/amazon/callback`.
- OAuth configuration status endpoint.
- Authorization list endpoint that never returns plaintext refresh tokens.
- One-time OAuth state sessions with expiry and consumed status.
- LWA authorization-code token exchange.
- Encrypted refresh-token persistence.
- Seller binding by `SellerAccount.amazon_seller_id == selling_partner_id` when possible.
- Tests for status, login redirect, callback success, callback failure, expired state, reused state, seller mismatch, and safe authorization listing.

V3 excludes:

- SP-API signed requests.
- SP-API Reports/Orders/Inventory data pulls.
- Amazon Ads API authorization or profile binding.
- Async jobs, report polling, rate-limit handling, retry backoff.
- Full login and public access control for internal pages.
- Reverse proxy configuration files.

Official references used for parameter names and flow:

- https://developer-docs.amazon.com/sp-api/docs/selling-partner-appstore-authorization-workflow?ld=ASXXSPAPIDirect
- https://developer-docs.amazon.com/sp-api/lang-es_ES/docs/website-authorization-workflow
- https://developer-docs.amazon.com/sp-api/lang-US/docs/authorize-public-applications

## File Structure

Create or modify these files:

```text
backend/pyproject.toml
backend/app/core/config.py
backend/app/api/deps.py
backend/app/api/routes/amazon_auth.py
backend/app/main.py
backend/app/domain/enums.py
backend/app/models/amazon.py
backend/app/models/__init__.py
backend/app/schemas/amazon.py
backend/app/services/amazon/__init__.py
backend/app/services/amazon/lwa.py
backend/app/services/amazon/oauth.py
backend/app/services/security/__init__.py
backend/app/services/security/tokens.py
backend/migrations/versions/20260528_0003_amazon_oauth.py
backend/tests/test_amazon_oauth_models.py
backend/tests/test_amazon_lwa.py
backend/tests/test_token_cipher.py
backend/tests/test_amazon_oauth_service.py
backend/tests/test_api_amazon_auth.py
README.md
```

Responsibilities:

- `core/config.py`: Amazon OAuth, LWA, and token-encryption configuration.
- `api/deps.py`: reusable `get_settings()` dependency so tests can override config cleanly.
- `api/routes/amazon_auth.py`: FastAPI endpoints and HTTP status mapping.
- `domain/enums.py`: explicit V3 OAuth session and authorization statuses.
- `models/amazon.py`: SQLAlchemy persistence models for OAuth sessions and authorizations.
- `schemas/amazon.py`: response models that exclude secrets.
- `services/amazon/lwa.py`: LWA token endpoint client.
- `services/amazon/oauth.py`: login/callback business rules.
- `services/security/tokens.py`: Fernet token encryption/decryption.
- `migrations/versions/20260528_0003_amazon_oauth.py`: Postgres/SQLite-compatible schema migration.
- `tests/*amazon*` and `tests/test_token_cipher.py`: TDD coverage for all V3 behavior.
- `README.md`: V3 configuration and callback URI instructions.

## Task 1: Config, Enums, Models, and Migration

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/domain/enums.py`
- Create: `backend/app/models/amazon.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_amazon_oauth_models.py`
- Create: `backend/migrations/versions/20260528_0003_amazon_oauth.py`

- [x] **Step 1: Write model and config tests**

Create `backend/tests/test_amazon_oauth_models.py`:

```python
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
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py -q
```

Expected: FAIL because `AmazonAuthorizationStatus`, `AmazonOAuthSessionStatus`, and `app.models.amazon` do not exist yet.

- [x] **Step 3: Add dependency and configuration**

Modify `backend/pyproject.toml` dependencies:

```toml
dependencies = [
  "alembic>=1.13.3",
  "cryptography>=43.0.0",
  "fastapi>=0.115.0",
  "httpx>=0.27.2",
  "jinja2>=3.1.4",
  "openpyxl>=3.1.5",
  "pandas>=2.2.3",
  "psycopg[binary]>=3.2.3",
  "pydantic-settings>=2.6.1",
  "python-multipart>=0.0.12",
  "sqlalchemy>=2.0.35",
  "uvicorn[standard]>=0.32.0",
  "xlsxwriter>=3.2.0"
]
```

Modify `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"
    STORAGE_ROOT: str = "backend/storage"
    LLM_PROVIDER: str = "mock"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str | None = None
    LLM_MODEL: str = "gpt-4.1-mini"
    LLM_TIMEOUT_SECONDS: int = 30
    PUBLIC_BASE_URL: str | None = None
    AMAZON_LWA_CLIENT_ID: str | None = None
    AMAZON_LWA_CLIENT_SECRET: str | None = None
    AMAZON_LWA_TOKEN_URL: str = "https://api.amazon.com/auth/o2/token"
    AMAZON_OAUTH_LOGIN_PATH: str = "/api/auth/amazon/login"
    AMAZON_OAUTH_REDIRECT_PATH: str = "/api/auth/amazon/callback"
    AMAZON_OAUTH_STATE_TTL_MINUTES: int = 10
    AMAZON_LWA_TIMEOUT_SECONDS: int = 15
    TOKEN_ENCRYPTION_KEY: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

- [x] **Step 4: Add enums**

Modify `backend/app/domain/enums.py`:

```python
class AmazonOAuthSessionStatus(StrEnum):
    CREATED = "created"
    CONSUMED = "consumed"
    EXPIRED = "expired"
    FAILED = "failed"


class AmazonAuthorizationStatus(StrEnum):
    ACTIVE = "active"
    FAILED = "failed"
    REVOKED = "revoked"
```

- [x] **Step 5: Add models**

Create `backend/app/models/amazon.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AmazonAuthorizationSession(TimestampMixin, Base):
    __tablename__ = "amazon_authorization_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    amazon_state: Mapped[str] = mapped_column(String(500))
    amazon_callback_uri: Mapped[str] = mapped_column(Text)
    selling_partner_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


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

Modify `backend/app/models/__init__.py`:

```python
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
```

Add both names to `__all__`.

- [x] **Step 6: Add Alembic migration**

Create `backend/migrations/versions/20260528_0003_amazon_oauth.py`:

```python
"""add amazon oauth tables

Revision ID: 20260528_0003
Revises: 20260528_0002
Create Date: 2026-05-28 00:00:02.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260528_0003"
down_revision = "20260528_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_table(
        "amazon_authorizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("selling_partner_id", sa.String(length=120), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=True),
        sa.Column("lwa_client_id", sa.String(length=255), nullable=False),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=False),
        sa.Column("token_type", sa.String(length=80), nullable=True),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["seller_account_id"],
            ["seller_accounts.id"],
            name=op.f("fk_amazon_authorizations_seller_account_id_seller_accounts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_amazon_authorizations")),
        sa.UniqueConstraint("selling_partner_id", name=op.f("uq_amazon_authorizations_selling_partner_id")),
    )
    op.create_index(
        op.f("ix_amazon_authorizations_selling_partner_id"),
        "amazon_authorizations",
        ["selling_partner_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorizations_seller_account_id"),
        "amazon_authorizations",
        ["seller_account_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorizations_authorized_at"),
        "amazon_authorizations",
        ["authorized_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_amazon_authorizations_status"),
        "amazon_authorizations",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_amazon_authorizations_status"), table_name="amazon_authorizations")
    op.drop_index(op.f("ix_amazon_authorizations_authorized_at"), table_name="amazon_authorizations")
    op.drop_index(op.f("ix_amazon_authorizations_seller_account_id"), table_name="amazon_authorizations")
    op.drop_index(op.f("ix_amazon_authorizations_selling_partner_id"), table_name="amazon_authorizations")
    op.drop_table("amazon_authorizations")
    op.drop_index(op.f("ix_amazon_authorization_sessions_expires_at"), table_name="amazon_authorization_sessions")
    op.drop_index(op.f("ix_amazon_authorization_sessions_status"), table_name="amazon_authorization_sessions")
    op.drop_index(op.f("ix_amazon_authorization_sessions_selling_partner_id"), table_name="amazon_authorization_sessions")
    op.drop_index(op.f("ix_amazon_authorization_sessions_state"), table_name="amazon_authorization_sessions")
    op.drop_table("amazon_authorization_sessions")
```

- [x] **Step 7: Run model tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py -q
```

Expected: PASS.

- [x] **Step 8: Commit Task 1**

Run:

```powershell
git add backend/pyproject.toml backend/app/core/config.py backend/app/domain/enums.py backend/app/models/amazon.py backend/app/models/__init__.py backend/migrations/versions/20260528_0003_amazon_oauth.py backend/tests/test_amazon_oauth_models.py
git commit -m "feat: add amazon oauth persistence"
```

## Task 2: Token Encryption and LWA Client

**Files:**
- Create: `backend/app/services/security/__init__.py`
- Create: `backend/app/services/security/tokens.py`
- Create: `backend/app/services/amazon/__init__.py`
- Create: `backend/app/services/amazon/lwa.py`
- Create: `backend/tests/test_token_cipher.py`
- Create: `backend/tests/test_amazon_lwa.py`

- [x] **Step 1: Write token encryption tests**

Create `backend/tests/test_token_cipher.py`:

```python
import pytest

from app.services.security.tokens import TokenCipher, TokenCipherConfigError

TEST_KEY = "MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY="


def test_token_cipher_encrypts_without_returning_plaintext() -> None:
    cipher = TokenCipher(TEST_KEY)

    encrypted = cipher.encrypt("refresh-token")

    assert encrypted != "refresh-token"
    assert cipher.decrypt(encrypted) == "refresh-token"


def test_token_cipher_rejects_missing_key() -> None:
    with pytest.raises(TokenCipherConfigError, match="TOKEN_ENCRYPTION_KEY is required"):
        TokenCipher(None)


def test_token_cipher_rejects_invalid_key() -> None:
    with pytest.raises(TokenCipherConfigError, match="valid Fernet key"):
        TokenCipher("not-a-fernet-key")
```

- [x] **Step 2: Run token tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_token_cipher.py -q
```

Expected: FAIL because `app.services.security.tokens` does not exist yet.

- [x] **Step 3: Implement token encryption**

Create `backend/app/services/security/__init__.py`:

```python
```

Create `backend/app/services/security/tokens.py`:

```python
from cryptography.fernet import Fernet, InvalidToken


class TokenCipherConfigError(ValueError):
    pass


class TokenCipher:
    def __init__(self, key: str | None) -> None:
        if not key:
            raise TokenCipherConfigError("TOKEN_ENCRYPTION_KEY is required")
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            raise TokenCipherConfigError("TOKEN_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, encrypted: str) -> str:
        try:
            return self._fernet.decrypt(encrypted.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("encrypted token could not be decrypted") from exc
```

- [x] **Step 4: Write LWA client tests**

Create `backend/tests/test_amazon_lwa.py`:

```python
import httpx
import pytest

from app.services.amazon.lwa import LWAClient, LWATokenExchangeError


def test_lwa_client_exchanges_authorization_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        assert request.method == "POST"
        assert request.url == "https://api.amazon.com/auth/o2/token"
        assert "grant_type=authorization_code" in body
        assert "code=spapi-code" in body
        assert "client_id=client-id" in body
        assert "client_secret=client-secret" in body
        assert "redirect_uri=https%3A%2F%2Fspapi.example.com%2Fapi%2Fauth%2Famazon%2Fcallback" in body
        return httpx.Response(
            200,
            json={
                "refresh_token": "refresh-token",
                "access_token": "access-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        timeout_seconds=15,
        transport=httpx.MockTransport(handler),
    )

    result = client.exchange_authorization_code(
        code="spapi-code",
        redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
    )

    assert result.refresh_token == "refresh-token"
    assert result.access_token == "access-token"
    assert result.token_type == "bearer"
    assert result.expires_in == 3600


def test_lwa_client_raises_clear_error_on_http_failure() -> None:
    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(400, text="bad code")),
    )

    with pytest.raises(LWATokenExchangeError, match="LWA token exchange failed"):
        client.exchange_authorization_code(
            code="bad-code",
            redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
        )


def test_lwa_client_requires_refresh_token_in_response() -> None:
    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(lambda _request: httpx.Response(200, json={})),
    )

    with pytest.raises(LWATokenExchangeError, match="refresh_token"):
        client.exchange_authorization_code(
            code="spapi-code",
            redirect_uri="https://spapi.example.com/api/auth/amazon/callback",
        )
```

- [x] **Step 5: Run LWA tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_lwa.py -q
```

Expected: FAIL because `app.services.amazon.lwa` does not exist yet.

- [x] **Step 6: Implement LWA client**

Create `backend/app/services/amazon/__init__.py`:

```python
```

Create `backend/app/services/amazon/lwa.py`:

```python
from dataclasses import dataclass

import httpx


class LWATokenExchangeError(Exception):
    pass


@dataclass(frozen=True)
class LWATokenResponse:
    refresh_token: str
    access_token: str | None
    token_type: str | None
    expires_in: int | None


class LWAClient:
    def __init__(
        self,
        *,
        token_url: str,
        client_id: str,
        client_secret: str,
        timeout_seconds: int = 15,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
        try:
            with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
                response = client.post(
                    self.token_url,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "redirect_uri": redirect_uri,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise LWATokenExchangeError(f"LWA token exchange failed: {exc}") from exc

        refresh_token = payload.get("refresh_token")
        if not refresh_token:
            raise LWATokenExchangeError("LWA token response did not include refresh_token")

        return LWATokenResponse(
            refresh_token=refresh_token,
            access_token=payload.get("access_token"),
            token_type=payload.get("token_type"),
            expires_in=payload.get("expires_in"),
        )
```

- [x] **Step 7: Run service tests**

Run:

```powershell
cd backend
python -m pytest tests/test_token_cipher.py tests/test_amazon_lwa.py -q
```

Expected: PASS.

- [x] **Step 8: Commit Task 2**

Run:

```powershell
git add backend/app/services/security backend/app/services/amazon backend/tests/test_token_cipher.py backend/tests/test_amazon_lwa.py
git commit -m "feat: add amazon oauth token services"
```

## Task 3: OAuth Business Service

**Files:**
- Create: `backend/app/services/amazon/oauth.py`
- Create: `backend/tests/test_amazon_oauth_service.py`

- [x] **Step 1: Write OAuth service tests**

Create `backend/tests/test_amazon_oauth_service.py`:

```python
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
```

- [x] **Step 2: Run service tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_service.py -q
```

Expected: FAIL because `app.services.amazon.oauth` does not exist yet.

- [x] **Step 3: Implement OAuth service**

Create `backend/app/services/amazon/oauth.py`:

```python
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.time import utc_now
from app.domain.enums import AmazonAuthorizationStatus, AmazonOAuthSessionStatus
from app.models.amazon import AmazonAuthorization, AmazonAuthorizationSession
from app.models.settings import SellerAccount
from app.services.amazon.lwa import LWATokenExchangeError, LWATokenResponse
from app.services.security.tokens import TokenCipher, TokenCipherConfigError


class LWAExchangeClient(Protocol):
    def exchange_authorization_code(self, *, code: str, redirect_uri: str) -> LWATokenResponse:
        ...


@dataclass(frozen=True)
class AmazonOAuthStatus:
    public_base_url_configured: bool
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    login_uri: str | None
    redirect_uri: str | None


@dataclass(frozen=True)
class LoginRedirect:
    state: str
    redirect_url: str


@dataclass(frozen=True)
class CallbackResult:
    authorization_id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str


class AmazonOAuthError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def build_public_url(settings: Settings, path: str) -> str | None:
    if not settings.PUBLIC_BASE_URL:
        return None
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/{path.lstrip('/')}"


def get_oauth_status(settings: Settings) -> AmazonOAuthStatus:
    return AmazonOAuthStatus(
        public_base_url_configured=bool(settings.PUBLIC_BASE_URL),
        lwa_client_id_configured=bool(settings.AMAZON_LWA_CLIENT_ID),
        lwa_client_secret_configured=bool(settings.AMAZON_LWA_CLIENT_SECRET),
        token_encryption_key_configured=bool(settings.TOKEN_ENCRYPTION_KEY),
        login_uri=build_public_url(settings, settings.AMAZON_OAUTH_LOGIN_PATH),
        redirect_uri=build_public_url(settings, settings.AMAZON_OAUTH_REDIRECT_PATH),
    )


def create_login_redirect(
    *,
    session: Session,
    settings: Settings,
    amazon_callback_uri: str,
    amazon_state: str,
    selling_partner_id: str,
) -> LoginRedirect:
    parsed = urlparse(amazon_callback_uri)
    if parsed.scheme != "https":
        raise AmazonOAuthError("amazon_callback_uri must use https")

    local_state = secrets.token_urlsafe(32)
    oauth_session = AmazonAuthorizationSession(
        state=local_state,
        amazon_state=amazon_state,
        amazon_callback_uri=amazon_callback_uri,
        selling_partner_id=selling_partner_id,
        status=AmazonOAuthSessionStatus.CREATED.value,
        expires_at=utc_now() + timedelta(minutes=settings.AMAZON_OAUTH_STATE_TTL_MINUTES),
    )
    session.add(oauth_session)
    session.flush()

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["state"] = local_state
    query["amazon_state"] = amazon_state
    redirect_url = urlunparse(parsed._replace(query=urlencode(query)))
    return LoginRedirect(state=local_state, redirect_url=redirect_url)


def handle_authorization_callback(
    *,
    session: Session,
    settings: Settings,
    state: str,
    selling_partner_id: str,
    spapi_oauth_code: str,
    lwa_client: LWAExchangeClient,
    token_cipher: TokenCipher,
) -> CallbackResult:
    oauth_session = session.scalar(
        select(AmazonAuthorizationSession).where(AmazonAuthorizationSession.state == state)
    )
    if oauth_session is None:
        raise AmazonOAuthError("state not found")
    if oauth_session.status != AmazonOAuthSessionStatus.CREATED.value:
        raise AmazonOAuthError("state has already been used")
    if oauth_session.expires_at < utc_now():
        oauth_session.status = AmazonOAuthSessionStatus.EXPIRED.value
        oauth_session.error_message = "state expired"
        session.flush()
        raise AmazonOAuthError("state expired")
    if oauth_session.selling_partner_id != selling_partner_id:
        raise AmazonOAuthError("selling_partner_id does not match authorization session")

    redirect_uri = build_public_url(settings, settings.AMAZON_OAUTH_REDIRECT_PATH)
    if not redirect_uri or not settings.AMAZON_LWA_CLIENT_ID or not settings.AMAZON_LWA_CLIENT_SECRET:
        raise AmazonOAuthError("Amazon OAuth configuration is incomplete", status_code=500)

    try:
        token_response = lwa_client.exchange_authorization_code(
            code=spapi_oauth_code,
            redirect_uri=redirect_uri,
        )
        refresh_token_encrypted = token_cipher.encrypt(token_response.refresh_token)
    except (LWATokenExchangeError, TokenCipherConfigError, ValueError) as exc:
        oauth_session.status = AmazonOAuthSessionStatus.FAILED.value
        oauth_session.error_message = str(exc)
        session.flush()
        raise AmazonOAuthError("LWA token exchange failed", status_code=502) from exc

    seller_account = session.scalar(
        select(SellerAccount).where(SellerAccount.amazon_seller_id == selling_partner_id)
    )
    authorization = session.scalar(
        select(AmazonAuthorization).where(
            AmazonAuthorization.selling_partner_id == selling_partner_id
        )
    )
    if authorization is None:
        authorization = AmazonAuthorization(
            selling_partner_id=selling_partner_id,
            seller_account=seller_account,
            lwa_client_id=settings.AMAZON_LWA_CLIENT_ID,
            refresh_token_encrypted=refresh_token_encrypted,
            token_type=token_response.token_type,
            authorized_at=utc_now(),
            status=AmazonAuthorizationStatus.ACTIVE.value,
        )
        session.add(authorization)
    else:
        authorization.seller_account = seller_account
        authorization.lwa_client_id = settings.AMAZON_LWA_CLIENT_ID
        authorization.refresh_token_encrypted = refresh_token_encrypted
        authorization.token_type = token_response.token_type
        authorization.authorized_at = utc_now()
        authorization.status = AmazonAuthorizationStatus.ACTIVE.value
        authorization.last_error = None

    oauth_session.status = AmazonOAuthSessionStatus.CONSUMED.value
    oauth_session.consumed_at = utc_now()
    session.flush()
    return CallbackResult(
        authorization_id=authorization.id,
        selling_partner_id=selling_partner_id,
        seller_account_id=authorization.seller_account_id,
        status=authorization.status,
    )
```

- [x] **Step 4: Run OAuth service tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_service.py -q
```

Expected: PASS.

- [x] **Step 5: Commit Task 3**

Run:

```powershell
git add backend/app/services/amazon/oauth.py backend/tests/test_amazon_oauth_service.py
git commit -m "feat: add amazon oauth service"
```

## Task 4: API Routes and Schemas

**Files:**
- Modify: `backend/app/api/deps.py`
- Create: `backend/app/api/routes/amazon_auth.py`
- Modify: `backend/app/main.py`
- Create: `backend/app/schemas/amazon.py`
- Create: `backend/tests/test_api_amazon_auth.py`

- [x] **Step 1: Write API tests**

Create `backend/tests/test_api_amazon_auth.py`:

```python
from collections.abc import Generator
from datetime import timedelta

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

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


def make_client() -> tuple[TestClient, object]:
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
    session_factory: object,
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
```

- [x] **Step 2: Run API tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_api_amazon_auth.py -q
```

Expected: FAIL because `app.api.routes.amazon_auth` and `app.schemas.amazon` do not exist yet.

- [x] **Step 3: Add dependencies and schemas**

Modify `backend/app/api/deps.py`:

```python
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.db import get_db_session


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_settings() -> Settings:
    return Settings()
```

Create `backend/app/schemas/amazon.py`:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AmazonOAuthStatusResponse(BaseModel):
    public_base_url_configured: bool
    lwa_client_id_configured: bool
    lwa_client_secret_configured: bool
    token_encryption_key_configured: bool
    login_uri: str | None
    redirect_uri: str | None


class AmazonAuthorizationCallbackResponse(BaseModel):
    authorization_id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str


class AmazonAuthorizationResponse(BaseModel):
    id: int
    selling_partner_id: str
    seller_account_id: int | None
    status: str
    authorized_at: datetime

    model_config = ConfigDict(from_attributes=True)
```

- [x] **Step 4: Add API router**

Create `backend/app/api/routes/amazon_auth.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.models.amazon import AmazonAuthorization
from app.schemas.amazon import (
    AmazonAuthorizationCallbackResponse,
    AmazonAuthorizationResponse,
    AmazonOAuthStatusResponse,
)
from app.services.amazon.lwa import LWAClient
from app.services.amazon.oauth import (
    AmazonOAuthError,
    create_login_redirect,
    get_oauth_status,
    handle_authorization_callback,
)
from app.services.security.tokens import TokenCipher, TokenCipherConfigError

router = APIRouter(prefix="/auth/amazon", tags=["amazon-auth"])
SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_lwa_client(settings: SettingsDep) -> LWAClient:
    if not settings.AMAZON_LWA_CLIENT_ID or not settings.AMAZON_LWA_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Amazon LWA configuration is incomplete")
    return LWAClient(
        token_url=settings.AMAZON_LWA_TOKEN_URL,
        client_id=settings.AMAZON_LWA_CLIENT_ID,
        client_secret=settings.AMAZON_LWA_CLIENT_SECRET,
        timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
    )


def get_token_cipher(settings: SettingsDep) -> TokenCipher:
    try:
        return TokenCipher(settings.TOKEN_ENCRYPTION_KEY)
    except TokenCipherConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/status", response_model=AmazonOAuthStatusResponse)
def status(settings: SettingsDep) -> AmazonOAuthStatusResponse:
    return AmazonOAuthStatusResponse.model_validate(get_oauth_status(settings).__dict__)


@router.get("/login")
def login(
    session: SessionDep,
    settings: SettingsDep,
    amazon_callback_uri: Annotated[str, Query(min_length=1)],
    amazon_state: Annotated[str, Query(min_length=1)],
    selling_partner_id: Annotated[str, Query(min_length=1)],
) -> RedirectResponse:
    try:
        result = create_login_redirect(
            session=session,
            settings=settings,
            amazon_callback_uri=amazon_callback_uri,
            amazon_state=amazon_state,
            selling_partner_id=selling_partner_id,
        )
    except AmazonOAuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    session.commit()
    return RedirectResponse(result.redirect_url, status_code=307)


@router.get("/callback", response_model=AmazonAuthorizationCallbackResponse)
def callback(
    session: SessionDep,
    settings: SettingsDep,
    lwa_client: Annotated[LWAClient, Depends(get_lwa_client)],
    token_cipher: Annotated[TokenCipher, Depends(get_token_cipher)],
    state: Annotated[str, Query(min_length=1)],
    selling_partner_id: Annotated[str, Query(min_length=1)],
    spapi_oauth_code: Annotated[str, Query(min_length=1)],
) -> AmazonAuthorizationCallbackResponse:
    try:
        result = handle_authorization_callback(
            session=session,
            settings=settings,
            state=state,
            selling_partner_id=selling_partner_id,
            spapi_oauth_code=spapi_oauth_code,
            lwa_client=lwa_client,
            token_cipher=token_cipher,
        )
    except AmazonOAuthError as exc:
        session.commit()
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    session.commit()
    return AmazonAuthorizationCallbackResponse(**result.__dict__)


@router.get("/authorizations", response_model=list[AmazonAuthorizationResponse])
def authorizations(session: SessionDep) -> list[AmazonAuthorization]:
    return list(session.scalars(select(AmazonAuthorization).order_by(AmazonAuthorization.id)))
```

Modify `backend/app/main.py`:

```python
from app.api.routes.amazon_auth import router as amazon_auth_router

# inside create_app()
app.include_router(amazon_auth_router, prefix="/api")
```

- [x] **Step 5: Run API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_amazon_auth.py -q
```

Expected: PASS.

- [x] **Step 6: Commit Task 4**

Run:

```powershell
git add backend/app/api/deps.py backend/app/api/routes/amazon_auth.py backend/app/main.py backend/app/schemas/amazon.py backend/tests/test_api_amazon_auth.py
git commit -m "feat: expose amazon oauth endpoints"
```

## Task 5: README and Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Modify `README.md` sections.

Add to `当前功能`:

```markdown
- Amazon SP-API 授权：提供 Website OAuth Login URI / Redirect URI，支持保存加密 refresh token，供后续 API 拉取版本使用。
```

Replace the current `暂未实现` sentence with:

```markdown
暂未实现：Amazon SP-API 自动拉取数据、Ads API 自动拉取、SP-API 签名请求、限流轮询、登录权限、异步任务队列、推送通知。
```

Add after `LLM 配置`:

```markdown
## Amazon SP-API OAuth 配置

V3 只实现授权回调和 refresh token 加密保存，不会自动拉取订单、库存、报表或广告数据。

`.env` 可配置：

```env
PUBLIC_BASE_URL=https://spapi.yourdomain.com
AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_OAUTH_LOGIN_PATH=/api/auth/amazon/login
AMAZON_OAUTH_REDIRECT_PATH=/api/auth/amazon/callback
AMAZON_OAUTH_STATE_TTL_MINUTES=10
AMAZON_LWA_TIMEOUT_SECONDS=15
TOKEN_ENCRYPTION_KEY=
```

生成 Fernet 加密 key：

```powershell
cd backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Amazon Developer Console 中配置：

- Login URI：`https://spapi.yourdomain.com/api/auth/amazon/login`
- Redirect URI：`https://spapi.yourdomain.com/api/auth/amazon/callback`

公网反向代理建议只放行：

- `/api/auth/amazon/login`
- `/api/auth/amazon/callback`
- `/api/auth/amazon/status`
- `/api/health`

不建议公网暴露后台页面、导入接口、报告接口、设置接口或 `/docs`。
```

- [ ] **Step 2: Run focused V3 tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_oauth_models.py tests/test_token_cipher.py tests/test_amazon_lwa.py tests/test_amazon_oauth_service.py tests/test_api_amazon_auth.py -q
```

Expected: PASS.

- [ ] **Step 3: Run all backend tests**

Run:

```powershell
cd backend
python -m pytest -q
```

Expected: PASS, existing 48 tests plus new V3 tests.

- [ ] **Step 4: Run lint**

Run:

```powershell
cd backend
python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 5: Verify migrations**

With Docker Postgres running:

```powershell
cd backend
python -m alembic upgrade head
```

Expected: migration reaches `20260528_0003 (head)`.

- [ ] **Step 6: Commit Task 5**

Run:

```powershell
git add README.md
git commit -m "docs: document amazon oauth setup"
```

- [ ] **Step 7: Push V3 branch**

Run:

```powershell
git status --short
git push -u origin codex/v3-spapi-oauth
```

Expected: branch pushed to GitHub. `.claude/` in the main checkout remains untouched and outside this worktree.
