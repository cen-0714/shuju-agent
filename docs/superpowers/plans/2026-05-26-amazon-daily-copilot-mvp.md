# Amazon Daily Copilot MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first internal MVP for a multi-store Amazon daily report Copilot using API-ready manual file imports.

**Architecture:** Implement a FastAPI monolith with clear service boundaries: data source adapters create `RawDataset` records, normalization converts raw rows into internal business tables, metrics are computed by code, reports are generated from metrics, and LLM summaries are validated before display. The MVP uses server-rendered internal pages for Dashboard, Data Import, Report Center, and Settings, while keeping JSON APIs available for future UI or automation.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, SQLite for tests, Jinja2, pandas, openpyxl, XlsxWriter, Pydantic Settings, pytest, ruff, Docker Compose.

---

## Scope Check

This plan implements the MVP defined in `docs/superpowers/specs/2026-05-26-amazon-daily-copilot-mvp-design.zh-CN.md`. It covers the API-ready manual import path, internal UI, metrics, report generation, LLM snapshot and validation, and API readiness stubs. It does not implement live SP-API or Amazon Ads API calls; it defines adapter contracts and stub adapters so those integrations can attach to the same raw dataset pipeline in a separate plan.

## File Structure

Create this structure:

```text
backend/
  pyproject.toml
  alembic.ini
  app/
    __init__.py
    main.py
    api/
      __init__.py
      deps.py
      routes/
        __init__.py
        health.py
        imports.py
        reports.py
        settings.py
    core/
      __init__.py
      config.py
      db.py
      errors.py
      storage.py
      time.py
    domain/
      __init__.py
      enums.py
    models/
      __init__.py
      base.py
      audit.py
      imports.py
      metrics.py
      normalized.py
      reports.py
      settings.py
    schemas/
      __init__.py
      imports.py
      reports.py
      settings.py
    services/
      __init__.py
      adapters/
        __init__.py
        base.py
        manual_file.py
        spapi_stub.py
        ads_stub.py
      imports/
        __init__.py
        parser.py
        schema_registry.py
        validator.py
        orchestrator.py
      normalization/
        __init__.py
        business.py
        inventory.py
        ads.py
      metrics/
        __init__.py
        definitions.py
        calculator.py
        freshness.py
      reports/
        __init__.py
        builder.py
        markdown.py
        excel.py
      llm/
        __init__.py
        provider.py
        snapshot.py
        validator.py
      audit.py
    web/
      __init__.py
      routes.py
      templates/
        base.html
        dashboard.html
        imports.html
        reports.html
        settings.html
      static/
        app.css
  migrations/
    env.py
    script.py.mako
  tests/
    conftest.py
    fixtures/
      business_report.csv
      inventory_report.csv
      ads_search_term_report.csv
    test_health.py
    test_models.py
    test_adapter_contract.py
    test_import_parser.py
    test_import_validator.py
    test_import_orchestrator.py
    test_normalization.py
    test_metrics.py
    test_reports.py
    test_llm.py
    test_api_imports.py
docker-compose.yml
.env.example
.gitignore
docs/api-readiness/amazon-api-readiness.md
```

Responsibilities:

- `backend/app/api`: JSON API endpoints and request dependencies.
- `backend/app/web`: internal server-rendered pages.
- `backend/app/core`: configuration, database, storage, time, and shared errors.
- `backend/app/domain`: enums shared by models, schemas, and services.
- `backend/app/models`: SQLAlchemy ORM tables.
- `backend/app/schemas`: Pydantic request and response schemas.
- `backend/app/services/adapters`: manual upload and future API adapter boundary.
- `backend/app/services/imports`: file parsing, schema detection, validation, and import orchestration.
- `backend/app/services/normalization`: report-specific normalized row builders.
- `backend/app/services/metrics`: metric definitions, freshness, and calculations.
- `backend/app/services/reports`: daily report JSON, Markdown, and Excel generation.
- `backend/app/services/llm`: snapshot building, provider interface, and output validation.
- `backend/tests`: unit and API tests with small fixture files.

## Task 1: Repository Foundation

**Files:**
- Create: `backend/pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Add pytest configuration and dependencies**

Create `backend/pyproject.toml`:

```toml
[project]
name = "amazon-daily-copilot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "alembic>=1.13.3",
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

[project.optional-dependencies]
dev = [
  "pytest>=8.3.3",
  "pytest-cov>=5.0.0",
  "ruff>=0.7.0"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 3: Add app skeleton**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Amazon Daily Copilot")
    app.include_router(health_router, prefix="/api")
    return app


app = create_app()
```

Create `backend/app/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Create empty package files:

```python
# backend/app/__init__.py
```

```python
# backend/app/api/__init__.py
```

```python
# backend/app/api/routes/__init__.py
```

- [ ] **Step 4: Add local environment files**

Create `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
backend/storage/
backend/.coverage
```

Create `.env.example`:

```dotenv
APP_ENV=local
DATABASE_URL=postgresql+psycopg://copilot:copilot@localhost:5432/copilot
TEST_DATABASE_URL=sqlite+pysqlite:///:memory:
STORAGE_ROOT=backend/storage
LLM_PROVIDER=mock
```

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: copilot
      POSTGRES_PASSWORD: copilot
      POSTGRES_DB: copilot
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  postgres-data:
```

- [ ] **Step 5: Run the health test**

Run:

```powershell
cd backend
python -m pip install -e ".[dev]"
python -m pytest tests/test_health.py -v
```

Expected: `1 passed`.

- [ ] **Step 6: Commit**

```powershell
git add .gitignore .env.example docker-compose.yml backend
git commit -m "feat: scaffold fastapi backend"
```

## Task 2: Domain Enums, Configuration, Database Session

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/db.py`
- Create: `backend/app/core/time.py`
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/api/deps.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Write failing tests for settings, enums, and DB session**

Create `backend/tests/test_models.py`:

```python
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import DataSource, DataStatus, Region, ReportType


def test_settings_defaults_to_local_storage() -> None:
    settings = Settings(DATABASE_URL="sqlite+pysqlite:///:memory:")

    assert settings.APP_ENV == "local"
    assert settings.STORAGE_ROOT.endswith("backend/storage")


def test_domain_enums_have_required_values() -> None:
    assert Region.AMERICAS.value == "americas"
    assert DataSource.MANUAL_FILE.value == "manual_file"
    assert ReportType.BUSINESS_REPORT.value == "business_report"
    assert DataStatus.PRELIMINARY.value == "preliminary"


def test_session_factory_executes_sql() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        value = session.execute(text("select 1")).scalar_one()

    assert value == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_models.py -v
```

Expected: FAIL with import errors for `app.core.config`, `app.core.db`, and `app.domain.enums`.

- [ ] **Step 3: Implement config and enums**

Create `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "local"
    DATABASE_URL: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    TEST_DATABASE_URL: str = "sqlite+pysqlite:///:memory:"
    STORAGE_ROOT: str = "backend/storage"
    LLM_PROVIDER: str = "mock"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

Create `backend/app/domain/enums.py`:

```python
from enum import StrEnum


class Region(StrEnum):
    AMERICAS = "americas"
    EUROPE = "europe"
    FAR_EAST = "far_east"


class DataSource(StrEnum):
    MANUAL_FILE = "manual_file"
    SP_API = "sp_api"
    ADS_API = "ads_api"


class ReportType(StrEnum):
    BUSINESS_REPORT = "business_report"
    INVENTORY_REPORT = "inventory_report"
    ADS_CAMPAIGN_REPORT = "ads_campaign_report"
    ADS_TARGETING_REPORT = "ads_targeting_report"
    ADS_SEARCH_TERM_REPORT = "ads_search_term_report"


class DataStatus(StrEnum):
    PRELIMINARY = "preliminary"
    STABLE = "stable"
    FINAL = "final"


class ImportJobStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"
```

- [ ] **Step 4: Implement database session helpers and API dependency**

Create `backend/app/core/db.py`:

```python
from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_sync_engine(database_url: str) -> Engine:
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, future=True)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


settings = Settings()
engine = create_sync_engine(settings.DATABASE_URL)
SessionLocal = create_session_factory(engine)


def get_db_session() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
```

Create `backend/app/api/deps.py`:

```python
from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.db import get_db_session


def get_session() -> Generator[Session, None, None]:
    yield from get_db_session()
```

Create `backend/app/core/time.py`:

```python
from datetime import UTC, date, datetime, timedelta

from app.domain.enums import DataStatus


def utc_now() -> datetime:
    return datetime.now(UTC)


def classify_data_status(report_date: date, today: date | None = None) -> DataStatus:
    current_day = today or utc_now().date()
    age_days = (current_day - report_date).days
    if age_days <= 0:
        return DataStatus.PRELIMINARY
    if age_days <= 2:
        return DataStatus.STABLE
    return DataStatus.FINAL


def date_range_days(start: date, end: date) -> int:
    return (end - start).days + 1
```

- [ ] **Step 5: Run tests**

Run:

```powershell
cd backend
python -m pytest tests/test_models.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/core backend/app/domain backend/app/api/deps.py backend/tests/test_models.py
git commit -m "feat: add backend configuration and domain enums"
```

## Task 3: ORM Models and Alembic Baseline

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/settings.py`
- Create: `backend/app/models/imports.py`
- Create: `backend/app/models/normalized.py`
- Create: `backend/app/models/metrics.py`
- Create: `backend/app/models/reports.py`
- Create: `backend/app/models/audit.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Extend model tests**

Append to `backend/tests/test_models.py`:

```python
from datetime import date

from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.settings import Marketplace, Organization, SellerAccount


def test_orm_can_create_core_records() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store A",
            amazon_seller_id="A1SELLER",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        job = ImportJob(
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            status="pending",
        )
        dataset = RawDataset(
            import_job=job,
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            schema_version="business_report.v1",
            raw_file_path="storage/raw/business.csv",
            raw_file_checksum="abc123",
            row_count=1,
            data_status="stable",
            data_version="2026-05-25-1",
        )
        session.add(dataset)
        session.commit()

        assert dataset.id is not None
        assert dataset.seller_account.display_name == "US Store A"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_models.py::test_orm_can_create_core_records -v
```

Expected: FAIL with missing model imports.

- [ ] **Step 3: Implement base model and settings models**

Create `backend/app/models/base.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.time import utc_now

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base(DeclarativeBase):
    metadata = metadata


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
```

Create `backend/app/models/settings.py`:

```python
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(80), unique=True)

    seller_accounts: Mapped[list["SellerAccount"]] = relationship(back_populates="organization")


class SellerAccount(TimestampMixin, Base):
    __tablename__ = "seller_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    display_name: Mapped[str] = mapped_column(String(200))
    amazon_seller_id: Mapped[str] = mapped_column(String(80))
    is_active: Mapped[bool] = mapped_column(default=True)

    organization: Mapped[Organization] = relationship(back_populates="seller_accounts")
    marketplaces: Mapped[list["Marketplace"]] = relationship(back_populates="seller_account")

    __table_args__ = (UniqueConstraint("organization_id", "amazon_seller_id"),)


class Marketplace(TimestampMixin, Base):
    __tablename__ = "marketplaces"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(40))
    country_code: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(String(80))
    currency_code: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(default=True)

    seller_account: Mapped[SellerAccount] = relationship(back_populates="marketplaces")

    __table_args__ = (UniqueConstraint("seller_account_id", "marketplace_id"),)
```

- [ ] **Step 4: Implement import, normalized, metrics, reports, and audit models**

Create `backend/app/models/imports.py`:

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    source: Mapped[str] = mapped_column(String(40))
    report_type: Mapped[str] = mapped_column(String(80))
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40))
    error_code: Mapped[str | None] = mapped_column(String(80))
    error_message: Mapped[str | None] = mapped_column(Text)

    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")
    raw_dataset: Mapped["RawDataset | None"] = relationship(back_populates="import_job")


class RawDataset(TimestampMixin, Base):
    __tablename__ = "raw_datasets"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_job_id: Mapped[int] = mapped_column(ForeignKey("import_jobs.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    source: Mapped[str] = mapped_column(String(40))
    report_type: Mapped[str] = mapped_column(String(80))
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    schema_version: Mapped[str] = mapped_column(String(80))
    raw_file_path: Mapped[str] = mapped_column(String(500))
    raw_file_checksum: Mapped[str] = mapped_column(String(128))
    row_count: Mapped[int] = mapped_column(Integer)
    data_status: Mapped[str] = mapped_column(String(40))
    data_version: Mapped[str] = mapped_column(String(120))
    source_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    import_job: Mapped[ImportJob] = relationship(back_populates="raw_dataset")
    seller_account = relationship("SellerAccount")
    marketplace = relationship("Marketplace")

    __table_args__ = (
        UniqueConstraint("seller_account_id", "marketplace_id", "report_type", "raw_file_checksum"),
    )


class RawReportRow(Base):
    __tablename__ = "raw_report_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    row_number: Mapped[int] = mapped_column(Integer)
    row_json: Mapped[str] = mapped_column(Text)
```

Create `backend/app/models/normalized.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class NormalizedBusinessDaily(Base):
    __tablename__ = "normalized_business_daily"

    id: Mapped[int] = mapped_column(primary_key=True)
    raw_dataset_id: Mapped[int] = mapped_column(ForeignKey("raw_datasets.id"))
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    report_date: Mapped[date] = mapped_column(Date)
    asin: Mapped[str | None] = mapped_column(String(20))
    sku: Mapped[str | None] = mapped_column(String(120))
    ordered_product_sales: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    units_ordered: Mapped[int] = mapped_column(default=0)
    sessions: Mapped[int] = mapped_column(default=0)
    page_views: Mapped[int] = mapped_column(default=0)
    conversion_rate: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    buy_box_percentage: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
```

Create `backend/app/models/metrics.py`:

```python
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class MetricDefinition(TimestampMixin, Base):
    __tablename__ = "metric_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(120))
    formula: Mapped[str] = mapped_column(Text)
    source_fields: Mapped[str] = mapped_column(Text)
    time_grain: Mapped[str] = mapped_column(String(40))
    currency_rule: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))

    __table_args__ = (UniqueConstraint("metric_name", "version"),)


class DailyMetric(Base):
    __tablename__ = "daily_metrics"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"))
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"))
    metric_date: Mapped[date] = mapped_column(Date)
    metric_name: Mapped[str] = mapped_column(String(120))
    metric_value: Mapped[Decimal] = mapped_column(Numeric(16, 4))
    metric_version: Mapped[str] = mapped_column(String(40))
    data_status: Mapped[str] = mapped_column(String(40))

    __table_args__ = (
        UniqueConstraint("seller_account_id", "marketplace_id", "metric_date", "metric_name"),
    )
```

Create `backend/app/models/reports.py`:

```python
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class DailyReport(TimestampMixin, Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"))
    report_date: Mapped[date] = mapped_column(Date)
    report_version: Mapped[int] = mapped_column(default=1)
    data_version: Mapped[str] = mapped_column(String(120))
    metric_definition_version: Mapped[str] = mapped_column(String(40))
    prompt_version: Mapped[str] = mapped_column(String(40))
    model_name: Mapped[str] = mapped_column(String(120))
    report_json: Mapped[str] = mapped_column(Text)
    markdown: Mapped[str] = mapped_column(Text)
    excel_path: Mapped[str | None] = mapped_column(String(500))

    __table_args__ = (UniqueConstraint("organization_id", "report_date", "report_version"),)
```

Create `backend/app/models/audit.py`:

```python
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    action: Mapped[str] = mapped_column(String(120))
    entity_type: Mapped[str] = mapped_column(String(120))
    entity_id: Mapped[str] = mapped_column(String(120))
    details_json: Mapped[str] = mapped_column(Text, default="{}")
```

Create `backend/app/models/__init__.py`:

```python
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset, RawReportRow
from app.models.metrics import DailyMetric, MetricDefinition
from app.models.normalized import NormalizedBusinessDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, Organization, SellerAccount

__all__ = [
    "AuditLog",
    "Base",
    "DailyMetric",
    "DailyReport",
    "ImportJob",
    "Marketplace",
    "MetricDefinition",
    "NormalizedBusinessDaily",
    "Organization",
    "RawDataset",
    "RawReportRow",
    "SellerAccount",
]
```

- [ ] **Step 5: Add Alembic baseline files**

Create `backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = postgresql+psycopg://copilot:copilot@localhost:5432/copilot

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
```

Create `backend/migrations/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import Settings
from app.models import Base

config = context.config
fileConfig(config.config_file_name)
config.set_main_option("sqlalchemy.url", Settings().DATABASE_URL)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 6: Run ORM tests**

Run:

```powershell
cd backend
python -m pytest tests/test_models.py -v
```

Expected: all tests in `test_models.py` pass.

- [ ] **Step 7: Create initial migration**

Run:

```powershell
cd backend
python -m alembic revision --autogenerate -m "create core tables"
python -m alembic upgrade head
```

Expected: Alembic creates one migration file under `backend/migrations/versions/` and applies it to local PostgreSQL.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/models backend/migrations backend/alembic.ini backend/tests/test_models.py
git commit -m "feat: add core database schema"
```

## Task 4: Adapter Contract and Manual File Adapter

**Files:**
- Create: `backend/app/schemas/imports.py`
- Create: `backend/app/services/adapters/base.py`
- Create: `backend/app/services/adapters/manual_file.py`
- Create: `backend/app/services/adapters/spapi_stub.py`
- Create: `backend/app/services/adapters/ads_stub.py`
- Create: `backend/tests/test_adapter_contract.py`

- [ ] **Step 1: Write failing adapter contract tests**

Create `backend/tests/test_adapter_contract.py`:

```python
from datetime import date
from pathlib import Path

from app.domain.enums import DataSource, DataStatus, ReportType
from app.services.adapters.base import RawDatasetEnvelope
from app.services.adapters.manual_file import ManualFileAdapter


def test_raw_dataset_envelope_contains_required_fields() -> None:
    envelope = RawDatasetEnvelope(
        seller_account_id=1,
        marketplace_id=2,
        region="americas",
        source=DataSource.MANUAL_FILE,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        schema_version="business_report.v1",
        raw_file_path="storage/raw/business.csv",
        raw_file_checksum="abc123",
        row_count=3,
        data_status=DataStatus.STABLE,
        data_version="2026-05-25-1",
        source_generated_at=None,
    )

    assert envelope.source == DataSource.MANUAL_FILE
    assert envelope.report_type == ReportType.BUSINESS_REPORT


def test_manual_file_adapter_builds_envelope(tmp_path: Path) -> None:
    file_path = tmp_path / "business.csv"
    file_path.write_text("date,sessions\n2026-05-25,10\n", encoding="utf-8")

    adapter = ManualFileAdapter(storage_root=tmp_path)
    envelope = adapter.build_envelope(
        source_file=file_path,
        seller_account_id=1,
        marketplace_id=2,
        region="americas",
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
        schema_version="business_report.v1",
        row_count=1,
        data_status=DataStatus.STABLE,
    )

    assert envelope.raw_file_checksum
    assert envelope.raw_file_path.endswith(".csv")
    assert envelope.data_version.startswith("2026-05-25")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_adapter_contract.py -v
```

Expected: FAIL with missing adapter modules.

- [ ] **Step 3: Implement import schemas and adapter base**

Create `backend/app/schemas/imports.py`:

```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.domain.enums import DataSource, DataStatus, ReportType


class ImportPreviewRequest(BaseModel):
    seller_account_id: int
    marketplace_id: int
    report_type: ReportType
    date_range_start: date
    date_range_end: date


class ImportPreviewResponse(BaseModel):
    detected_schema_version: str
    row_count: int
    required_columns_present: bool
    missing_columns: list[str]
    sample_rows: list[dict[str, str]]


class RawDatasetEnvelopeSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seller_account_id: int
    marketplace_id: int
    region: str
    source: DataSource
    report_type: ReportType
    date_range_start: date
    date_range_end: date
    schema_version: str
    raw_file_path: str
    raw_file_checksum: str
    row_count: int
    data_status: DataStatus
    data_version: str
    source_generated_at: datetime | None
```

Create `backend/app/services/adapters/base.py`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from app.domain.enums import DataSource, DataStatus, ReportType


@dataclass(frozen=True)
class RawDatasetEnvelope:
    seller_account_id: int
    marketplace_id: int
    region: str
    source: DataSource
    report_type: ReportType
    date_range_start: date
    date_range_end: date
    schema_version: str
    raw_file_path: str
    raw_file_checksum: str
    row_count: int
    data_status: DataStatus
    data_version: str
    source_generated_at: datetime | None


class DataSourceAdapter(ABC):
    source: DataSource

    @abstractmethod
    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise NotImplementedError
```

- [ ] **Step 4: Implement manual file adapter and API stubs**

Create `backend/app/services/adapters/manual_file.py`:

```python
from datetime import date
from hashlib import sha256
from pathlib import Path

from app.domain.enums import DataSource, DataStatus, ReportType
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class ManualFileAdapter(DataSourceAdapter):
    source = DataSource.MANUAL_FILE

    def __init__(self, storage_root: Path | str) -> None:
        self.storage_root = Path(storage_root)

    def build_envelope(
        self,
        *,
        source_file: Path,
        seller_account_id: int,
        marketplace_id: int,
        region: str,
        report_type: ReportType,
        date_range_start: date,
        date_range_end: date,
        schema_version: str,
        row_count: int,
        data_status: DataStatus,
    ) -> RawDatasetEnvelope:
        checksum = self._checksum(source_file)
        relative_path = f"raw/{seller_account_id}/{marketplace_id}/{checksum}{source_file.suffix}"
        data_version = f"{date_range_end.isoformat()}-{checksum[:8]}"
        return RawDatasetEnvelope(
            seller_account_id=seller_account_id,
            marketplace_id=marketplace_id,
            region=region,
            source=self.source,
            report_type=report_type,
            date_range_start=date_range_start,
            date_range_end=date_range_end,
            schema_version=schema_version,
            raw_file_path=relative_path,
            raw_file_checksum=checksum,
            row_count=row_count,
            data_status=data_status,
            data_version=data_version,
            source_generated_at=None,
        )

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()
```

Create `backend/app/services/adapters/spapi_stub.py`:

```python
from app.domain.enums import DataSource
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class SPAPIReportAdapter(DataSourceAdapter):
    source = DataSource.SP_API

    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise RuntimeError("SP-API adapter is not enabled in the MVP")
```

Create `backend/app/services/adapters/ads_stub.py`:

```python
from app.domain.enums import DataSource
from app.services.adapters.base import DataSourceAdapter, RawDatasetEnvelope


class AdsAPIReportAdapter(DataSourceAdapter):
    source = DataSource.ADS_API

    def build_envelope(self, *args: object, **kwargs: object) -> RawDatasetEnvelope:
        raise RuntimeError("Amazon Ads API adapter is not enabled in the MVP")
```

- [ ] **Step 5: Run adapter tests**

Run:

```powershell
cd backend
python -m pytest tests/test_adapter_contract.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/schemas/imports.py backend/app/services/adapters backend/tests/test_adapter_contract.py
git commit -m "feat: define data source adapter contract"
```

## Task 5: File Parser and Schema Registry

**Files:**
- Create: `backend/app/core/errors.py`
- Create: `backend/app/services/imports/schema_registry.py`
- Create: `backend/app/services/imports/parser.py`
- Create: `backend/tests/fixtures/business_report.csv`
- Create: `backend/tests/fixtures/inventory_report.csv`
- Create: `backend/tests/fixtures/ads_search_term_report.csv`
- Create: `backend/tests/test_import_parser.py`

- [ ] **Step 1: Create fixture files**

Create `backend/tests/fixtures/business_report.csv`:

```csv
Date,ASIN,SKU,Sessions,Page Views,Units Ordered,Ordered Product Sales,Conversion Rate,Buy Box Percentage
2026-05-25,B0TESTASIN,SKU-1,100,180,12,240.00,0.12,0.98
```

Create `backend/tests/fixtures/inventory_report.csv`:

```csv
sku,asin,fulfillment-channel,quantity,status,price
SKU-1,B0TESTASIN,AMAZON_NA,22,Active,19.99
```

Create `backend/tests/fixtures/ads_search_term_report.csv`:

```csv
Date,Campaign Name,Search Term,Impressions,Clicks,Spend,7 Day Total Sales,7 Day Total Orders (#)
2026-05-25,Campaign A,coffee grinder,1000,40,32.50,120.00,4
```

- [ ] **Step 2: Write failing parser tests**

Create `backend/tests/test_import_parser.py`:

```python
from pathlib import Path

from app.domain.enums import ReportType
from app.services.imports.parser import parse_report_file
from app.services.imports.schema_registry import detect_schema

FIXTURES = Path(__file__).parent / "fixtures"


def test_detects_business_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "business_report.csv")
    schema = detect_schema(ReportType.BUSINESS_REPORT, parsed.headers)

    assert schema.version == "business_report.v1"
    assert parsed.row_count == 1


def test_detects_inventory_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "inventory_report.csv")
    schema = detect_schema(ReportType.INVENTORY_REPORT, parsed.headers)

    assert schema.version == "inventory_report.v1"


def test_detects_ads_search_term_report_schema() -> None:
    parsed = parse_report_file(FIXTURES / "ads_search_term_report.csv")
    schema = detect_schema(ReportType.ADS_SEARCH_TERM_REPORT, parsed.headers)

    assert schema.version == "ads_search_term_report.v1"
    assert parsed.sample_rows[0]["Search Term"] == "coffee grinder"
```

- [ ] **Step 3: Run parser tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_import_parser.py -v
```

Expected: FAIL with missing parser modules.

- [ ] **Step 4: Implement shared errors**

Create `backend/app/core/errors.py`:

```python
class AppError(Exception):
    code = "app_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(AppError):
    code = "unsupported_file_type"


class UnknownSchemaError(AppError):
    code = "unknown_schema"


class MissingRequiredColumnsError(AppError):
    code = "missing_required_columns"

    def __init__(self, missing_columns: list[str]) -> None:
        self.missing_columns = missing_columns
        super().__init__(f"Missing required columns: {', '.join(missing_columns)}")
```

- [ ] **Step 5: Implement parser and schema registry**

Create `backend/app/services/imports/parser.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from app.core.errors import UnsupportedFileTypeError


@dataclass(frozen=True)
class ParsedReportFile:
    headers: list[str]
    rows: list[dict[str, str]]
    row_count: int
    sample_rows: list[dict[str, str]]


def parse_report_file(path: Path) -> ParsedReportFile:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        frame = pd.read_csv(path, dtype=str).fillna("")
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=str).fillna("")
    else:
        raise UnsupportedFileTypeError(f"Unsupported file type: {suffix}")

    rows = [{str(key): str(value) for key, value in row.items()} for row in frame.to_dict("records")]
    return ParsedReportFile(
        headers=[str(column) for column in frame.columns],
        rows=rows,
        row_count=len(rows),
        sample_rows=rows[:5],
    )
```

Create `backend/app/services/imports/schema_registry.py`:

```python
from dataclasses import dataclass

from app.core.errors import UnknownSchemaError
from app.domain.enums import ReportType


@dataclass(frozen=True)
class ReportSchema:
    version: str
    report_type: ReportType
    required_columns: set[str]
    aliases: dict[str, str]


SCHEMAS: dict[ReportType, list[ReportSchema]] = {
    ReportType.BUSINESS_REPORT: [
        ReportSchema(
            version="business_report.v1",
            report_type=ReportType.BUSINESS_REPORT,
            required_columns={"Date", "Sessions", "Units Ordered", "Ordered Product Sales"},
            aliases={
                "Date": "report_date",
                "ASIN": "asin",
                "SKU": "sku",
                "Sessions": "sessions",
                "Page Views": "page_views",
                "Units Ordered": "units_ordered",
                "Ordered Product Sales": "ordered_product_sales",
                "Conversion Rate": "conversion_rate",
                "Buy Box Percentage": "buy_box_percentage",
            },
        )
    ],
    ReportType.INVENTORY_REPORT: [
        ReportSchema(
            version="inventory_report.v1",
            report_type=ReportType.INVENTORY_REPORT,
            required_columns={"sku", "asin", "quantity", "status"},
            aliases={
                "sku": "sku",
                "asin": "asin",
                "fulfillment-channel": "fulfillment_channel",
                "quantity": "available_quantity",
                "status": "listing_status",
                "price": "price",
            },
        )
    ],
    ReportType.ADS_SEARCH_TERM_REPORT: [
        ReportSchema(
            version="ads_search_term_report.v1",
            report_type=ReportType.ADS_SEARCH_TERM_REPORT,
            required_columns={"Date", "Campaign Name", "Search Term", "Clicks", "Spend"},
            aliases={
                "Date": "report_date",
                "Campaign Name": "campaign_name",
                "Search Term": "search_term",
                "Impressions": "impressions",
                "Clicks": "clicks",
                "Spend": "spend",
                "7 Day Total Sales": "attributed_sales",
                "7 Day Total Orders (#)": "attributed_orders",
            },
        )
    ],
}


def detect_schema(report_type: ReportType, headers: list[str]) -> ReportSchema:
    header_set = set(headers)
    for schema in SCHEMAS.get(report_type, []):
        if schema.required_columns.issubset(header_set):
            return schema
    raise UnknownSchemaError(f"No schema matched report type {report_type}")
```

- [ ] **Step 6: Run parser tests**

Run:

```powershell
cd backend
python -m pytest tests/test_import_parser.py -v
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/core/errors.py backend/app/services/imports backend/tests/fixtures backend/tests/test_import_parser.py
git commit -m "feat: parse manual report files"
```

## Task 6: Import Validation and Orchestration

**Files:**
- Create: `backend/app/core/storage.py`
- Create: `backend/app/services/imports/validator.py`
- Create: `backend/app/services/imports/orchestrator.py`
- Modify: `backend/app/schemas/imports.py`
- Test: `backend/tests/test_import_validator.py`
- Test: `backend/tests/test_import_orchestrator.py`

- [ ] **Step 1: Write failing validation tests**

Create `backend/tests/test_import_validator.py`:

```python
from app.core.errors import MissingRequiredColumnsError
from app.domain.enums import ReportType
from app.services.imports.schema_registry import detect_schema
from app.services.imports.validator import validate_required_columns


def test_validate_required_columns_passes() -> None:
    schema = detect_schema(
        ReportType.BUSINESS_REPORT,
        ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"],
    )

    validate_required_columns(schema, ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"])


def test_validate_required_columns_raises_with_missing_names() -> None:
    schema = detect_schema(
        ReportType.BUSINESS_REPORT,
        ["Date", "Sessions", "Units Ordered", "Ordered Product Sales"],
    )

    try:
        validate_required_columns(schema, ["Date", "Sessions"])
    except MissingRequiredColumnsError as exc:
        assert exc.missing_columns == ["Ordered Product Sales", "Units Ordered"]
    else:
        raise AssertionError("Expected MissingRequiredColumnsError")
```

- [ ] **Step 2: Write failing orchestrator test**

Create `backend/tests/test_import_orchestrator.py`:

```python
from datetime import date
from pathlib import Path

from app.domain.enums import DataStatus, ReportType
from app.services.imports.orchestrator import preview_manual_import


def test_preview_manual_import_returns_schema_and_rows() -> None:
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    preview = preview_manual_import(
        file_path=fixture,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date(2026, 5, 25),
        date_range_end=date(2026, 5, 25),
    )

    assert preview.detected_schema_version == "business_report.v1"
    assert preview.row_count == 1
    assert preview.required_columns_present is True
    assert preview.data_status == DataStatus.STABLE
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_import_validator.py tests/test_import_orchestrator.py -v
```

Expected: FAIL with missing validator and orchestrator modules.

- [ ] **Step 4: Implement storage and validator**

Create `backend/app/core/storage.py`:

```python
from pathlib import Path
from shutil import copyfile


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def save_file(self, source: Path, relative_path: str) -> Path:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        copyfile(source, target)
        return target
```

Create `backend/app/services/imports/validator.py`:

```python
from app.core.errors import MissingRequiredColumnsError
from app.services.imports.schema_registry import ReportSchema


def validate_required_columns(schema: ReportSchema, headers: list[str]) -> None:
    missing = sorted(schema.required_columns - set(headers))
    if missing:
        raise MissingRequiredColumnsError(missing)
```

- [ ] **Step 5: Implement preview orchestrator**

Modify `backend/app/schemas/imports.py` by replacing `ImportPreviewResponse` with:

```python
class ImportPreviewResponse(BaseModel):
    detected_schema_version: str
    row_count: int
    required_columns_present: bool
    missing_columns: list[str]
    sample_rows: list[dict[str, str]]
    data_status: DataStatus
```

Create `backend/app/services/imports/orchestrator.py`:

```python
from datetime import date
from pathlib import Path

from app.core.errors import MissingRequiredColumnsError
from app.core.time import classify_data_status
from app.domain.enums import ReportType
from app.schemas.imports import ImportPreviewResponse
from app.services.imports.parser import parse_report_file
from app.services.imports.schema_registry import detect_schema
from app.services.imports.validator import validate_required_columns


def preview_manual_import(
    *,
    file_path: Path,
    report_type: ReportType,
    date_range_start: date,
    date_range_end: date,
) -> ImportPreviewResponse:
    parsed = parse_report_file(file_path)
    schema = detect_schema(report_type, parsed.headers)
    missing_columns: list[str] = []
    try:
        validate_required_columns(schema, parsed.headers)
    except MissingRequiredColumnsError as exc:
        missing_columns = exc.missing_columns

    return ImportPreviewResponse(
        detected_schema_version=schema.version,
        row_count=parsed.row_count,
        required_columns_present=not missing_columns,
        missing_columns=missing_columns,
        sample_rows=parsed.sample_rows,
        data_status=classify_data_status(date_range_end),
    )
```

- [ ] **Step 6: Run import tests**

Run:

```powershell
cd backend
python -m pytest tests/test_import_validator.py tests/test_import_orchestrator.py -v
```

Expected: `3 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/core/storage.py backend/app/services/imports backend/app/schemas/imports.py backend/tests/test_import_validator.py backend/tests/test_import_orchestrator.py
git commit -m "feat: validate manual import previews"
```

## Task 7: Normalization Pipeline

**Files:**
- Create: `backend/app/services/normalization/business.py`
- Create: `backend/app/services/normalization/inventory.py`
- Create: `backend/app/services/normalization/ads.py`
- Test: `backend/tests/test_normalization.py`

- [ ] **Step 1: Write failing normalization tests**

Create `backend/tests/test_normalization.py`:

```python
from decimal import Decimal

from app.services.normalization.ads import normalize_ads_search_term_row
from app.services.normalization.business import normalize_business_row
from app.services.normalization.inventory import normalize_inventory_row


def test_normalize_business_row() -> None:
    row = {
        "Date": "2026-05-25",
        "ASIN": "B0TESTASIN",
        "SKU": "SKU-1",
        "Sessions": "100",
        "Page Views": "180",
        "Units Ordered": "12",
        "Ordered Product Sales": "240.00",
        "Conversion Rate": "0.12",
        "Buy Box Percentage": "0.98",
    }

    normalized = normalize_business_row(row)

    assert normalized.report_date.isoformat() == "2026-05-25"
    assert normalized.ordered_product_sales == Decimal("240.00")
    assert normalized.units_ordered == 12


def test_normalize_inventory_row() -> None:
    row = {
        "sku": "SKU-1",
        "asin": "B0TESTASIN",
        "fulfillment-channel": "AMAZON_NA",
        "quantity": "22",
        "status": "Active",
        "price": "19.99",
    }

    normalized = normalize_inventory_row(row)

    assert normalized.sku == "SKU-1"
    assert normalized.available_quantity == 22
    assert normalized.is_active_listing is True


def test_normalize_ads_search_term_row() -> None:
    row = {
        "Date": "2026-05-25",
        "Campaign Name": "Campaign A",
        "Search Term": "coffee grinder",
        "Impressions": "1000",
        "Clicks": "40",
        "Spend": "32.50",
        "7 Day Total Sales": "120.00",
        "7 Day Total Orders (#)": "4",
    }

    normalized = normalize_ads_search_term_row(row)

    assert normalized.search_term == "coffee grinder"
    assert normalized.spend == Decimal("32.50")
    assert normalized.attributed_orders == 4
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_normalization.py -v
```

Expected: FAIL with missing normalization modules.

- [ ] **Step 3: Implement business normalization**

Create `backend/app/services/normalization/business.py`:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedBusinessRow:
    report_date: date
    asin: str | None
    sku: str | None
    ordered_product_sales: Decimal
    units_ordered: int
    sessions: int
    page_views: int
    conversion_rate: Decimal | None
    buy_box_percentage: Decimal | None


def normalize_business_row(row: dict[str, str]) -> NormalizedBusinessRow:
    return NormalizedBusinessRow(
        report_date=date.fromisoformat(row["Date"]),
        asin=row.get("ASIN") or None,
        sku=row.get("SKU") or None,
        ordered_product_sales=Decimal(row.get("Ordered Product Sales") or "0"),
        units_ordered=int(row.get("Units Ordered") or 0),
        sessions=int(row.get("Sessions") or 0),
        page_views=int(row.get("Page Views") or 0),
        conversion_rate=_optional_decimal(row.get("Conversion Rate")),
        buy_box_percentage=_optional_decimal(row.get("Buy Box Percentage")),
    )


def _optional_decimal(value: str | None) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(value)
```

- [ ] **Step 4: Implement inventory and ads normalization**

Create `backend/app/services/normalization/inventory.py`:

```python
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedInventoryRow:
    sku: str
    asin: str
    fulfillment_channel: str | None
    available_quantity: int
    listing_status: str
    price: Decimal | None
    is_active_listing: bool


def normalize_inventory_row(row: dict[str, str]) -> NormalizedInventoryRow:
    status = row.get("status", "")
    return NormalizedInventoryRow(
        sku=row["sku"],
        asin=row["asin"],
        fulfillment_channel=row.get("fulfillment-channel") or None,
        available_quantity=int(row.get("quantity") or 0),
        listing_status=status,
        price=Decimal(row["price"]) if row.get("price") else None,
        is_active_listing=status.lower() == "active",
    )
```

Create `backend/app/services/normalization/ads.py`:

```python
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class NormalizedAdsSearchTermRow:
    report_date: date
    campaign_name: str
    search_term: str
    impressions: int
    clicks: int
    spend: Decimal
    attributed_sales: Decimal
    attributed_orders: int


def normalize_ads_search_term_row(row: dict[str, str]) -> NormalizedAdsSearchTermRow:
    return NormalizedAdsSearchTermRow(
        report_date=date.fromisoformat(row["Date"]),
        campaign_name=row["Campaign Name"],
        search_term=row["Search Term"],
        impressions=int(row.get("Impressions") or 0),
        clicks=int(row.get("Clicks") or 0),
        spend=Decimal(row.get("Spend") or "0"),
        attributed_sales=Decimal(row.get("7 Day Total Sales") or "0"),
        attributed_orders=int(row.get("7 Day Total Orders (#)") or 0),
    )
```

- [ ] **Step 5: Run normalization tests**

Run:

```powershell
cd backend
python -m pytest tests/test_normalization.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/normalization backend/tests/test_normalization.py
git commit -m "feat: normalize supported report rows"
```

## Task 8: Metrics and Data Freshness

**Files:**
- Create: `backend/app/services/metrics/definitions.py`
- Create: `backend/app/services/metrics/freshness.py`
- Create: `backend/app/services/metrics/calculator.py`
- Test: `backend/tests/test_metrics.py`

- [ ] **Step 1: Write failing metrics tests**

Create `backend/tests/test_metrics.py`:

```python
from datetime import date
from decimal import Decimal

from app.services.metrics.calculator import calculate_ads_metrics, calculate_business_metrics
from app.services.metrics.definitions import metric_definitions
from app.services.metrics.freshness import freshness_for_report_date


def test_metric_definitions_include_core_metrics() -> None:
    names = {definition.metric_name for definition in metric_definitions()}

    assert "ordered_product_sales" in names
    assert "acos" in names
    assert "roas" in names


def test_calculate_business_metrics() -> None:
    metrics = calculate_business_metrics(
        ordered_product_sales=Decimal("240.00"),
        units_ordered=12,
        sessions=100,
    )

    assert metrics["ordered_product_sales"] == Decimal("240.00")
    assert metrics["conversion_rate"] == Decimal("0.1200")


def test_calculate_ads_metrics() -> None:
    metrics = calculate_ads_metrics(
        spend=Decimal("32.50"),
        attributed_sales=Decimal("120.00"),
        clicks=40,
        impressions=1000,
        attributed_orders=4,
    )

    assert metrics["acos"] == Decimal("0.2708")
    assert metrics["roas"] == Decimal("3.6923")
    assert metrics["ctr"] == Decimal("0.0400")


def test_freshness_for_report_date() -> None:
    assert freshness_for_report_date(date(2026, 5, 26), today=date(2026, 5, 26)).value == "preliminary"
    assert freshness_for_report_date(date(2026, 5, 25), today=date(2026, 5, 26)).value == "stable"
    assert freshness_for_report_date(date(2026, 5, 20), today=date(2026, 5, 26)).value == "final"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_metrics.py -v
```

Expected: FAIL with missing metrics modules.

- [ ] **Step 3: Implement metric definitions and freshness**

Create `backend/app/services/metrics/definitions.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDefinitionSeed:
    metric_name: str
    formula: str
    source_fields: tuple[str, ...]
    time_grain: str
    currency_rule: str
    version: str


def metric_definitions() -> list[MetricDefinitionSeed]:
    return [
        MetricDefinitionSeed("ordered_product_sales", "sum sales", ("ordered_product_sales",), "day", "source_currency", "v1"),
        MetricDefinitionSeed("units_ordered", "sum units", ("units_ordered",), "day", "none", "v1"),
        MetricDefinitionSeed("conversion_rate", "units_ordered / sessions", ("units_ordered", "sessions"), "day", "none", "v1"),
        MetricDefinitionSeed("spend", "sum spend", ("spend",), "day", "source_currency", "v1"),
        MetricDefinitionSeed("acos", "spend / attributed_sales", ("spend", "attributed_sales"), "day", "none", "v1"),
        MetricDefinitionSeed("roas", "attributed_sales / spend", ("attributed_sales", "spend"), "day", "none", "v1"),
        MetricDefinitionSeed("ctr", "clicks / impressions", ("clicks", "impressions"), "day", "none", "v1"),
        MetricDefinitionSeed("cvr", "attributed_orders / clicks", ("attributed_orders", "clicks"), "day", "none", "v1"),
    ]
```

Create `backend/app/services/metrics/freshness.py`:

```python
from datetime import date

from app.core.time import classify_data_status
from app.domain.enums import DataStatus


def freshness_for_report_date(report_date: date, today: date | None = None) -> DataStatus:
    return classify_data_status(report_date, today=today)
```

- [ ] **Step 4: Implement metric calculators**

Create `backend/app/services/metrics/calculator.py`:

```python
from decimal import Decimal, ROUND_HALF_UP


def calculate_business_metrics(
    *,
    ordered_product_sales: Decimal,
    units_ordered: int,
    sessions: int,
) -> dict[str, Decimal]:
    return {
        "ordered_product_sales": ordered_product_sales,
        "units_ordered": Decimal(units_ordered),
        "sessions": Decimal(sessions),
        "conversion_rate": _ratio(Decimal(units_ordered), Decimal(sessions)),
    }


def calculate_ads_metrics(
    *,
    spend: Decimal,
    attributed_sales: Decimal,
    clicks: int,
    impressions: int,
    attributed_orders: int,
) -> dict[str, Decimal]:
    return {
        "spend": spend,
        "attributed_sales": attributed_sales,
        "clicks": Decimal(clicks),
        "impressions": Decimal(impressions),
        "attributed_orders": Decimal(attributed_orders),
        "acos": _ratio(spend, attributed_sales),
        "roas": _ratio(attributed_sales, spend),
        "ctr": _ratio(Decimal(clicks), Decimal(impressions)),
        "cvr": _ratio(Decimal(attributed_orders), Decimal(clicks)),
    }


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator == 0:
        return Decimal("0.0000")
    return (numerator / denominator).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

- [ ] **Step 5: Run metrics tests**

Run:

```powershell
cd backend
python -m pytest tests/test_metrics.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/metrics backend/tests/test_metrics.py
git commit -m "feat: calculate daily operating metrics"
```

## Task 9: Daily Report Builder, Markdown, and Excel

**Files:**
- Create: `backend/app/schemas/reports.py`
- Create: `backend/app/services/reports/builder.py`
- Create: `backend/app/services/reports/markdown.py`
- Create: `backend/app/services/reports/excel.py`
- Test: `backend/tests/test_reports.py`

- [ ] **Step 1: Write failing report tests**

Create `backend/tests/test_reports.py`:

```python
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.schemas.reports import StoreDailySummary
from app.services.reports.builder import build_daily_report
from app.services.reports.excel import write_daily_report_excel
from app.services.reports.markdown import render_daily_report_markdown


def test_build_daily_report_contains_store_summary() -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[
            StoreDailySummary(
                seller_account_id=1,
                seller_name="US Store A",
                marketplace_id="ATVPDKIKX0DER",
                ordered_product_sales=Decimal("240.00"),
                units_ordered=12,
                ad_spend=Decimal("32.50"),
                ad_sales=Decimal("120.00"),
                acos=Decimal("0.2708"),
                data_status="stable",
            )
        ],
        warnings=["inventory report missing"],
    )

    assert report.report_date.isoformat() == "2026-05-25"
    assert report.totals["ordered_product_sales"] == Decimal("240.00")
    assert report.warnings == ["inventory report missing"]


def test_render_daily_report_markdown() -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[],
        warnings=[],
    )

    markdown = render_daily_report_markdown(report)

    assert "# Daily Amazon Report - 2026-05-25" in markdown
    assert "Data Freshness" in markdown


def test_write_daily_report_excel(tmp_path: Path) -> None:
    report = build_daily_report(
        report_date=date(2026, 5, 25),
        store_summaries=[],
        warnings=[],
    )
    output = tmp_path / "daily.xlsx"

    write_daily_report_excel(report, output)

    assert output.exists()
    assert output.stat().st_size > 0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_reports.py -v
```

Expected: FAIL with missing report schemas and services.

- [ ] **Step 3: Implement report schemas and builder**

Create `backend/app/schemas/reports.py`:

```python
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class StoreDailySummary(BaseModel):
    seller_account_id: int
    seller_name: str
    marketplace_id: str
    ordered_product_sales: Decimal = Decimal("0")
    units_ordered: int = 0
    ad_spend: Decimal = Decimal("0")
    ad_sales: Decimal = Decimal("0")
    acos: Decimal = Decimal("0")
    data_status: str


class DailyReportDocument(BaseModel):
    report_date: date
    store_summaries: list[StoreDailySummary]
    totals: dict[str, Decimal]
    warnings: list[str]
```

Create `backend/app/services/reports/builder.py`:

```python
from datetime import date
from decimal import Decimal

from app.schemas.reports import DailyReportDocument, StoreDailySummary


def build_daily_report(
    *,
    report_date: date,
    store_summaries: list[StoreDailySummary],
    warnings: list[str],
) -> DailyReportDocument:
    totals = {
        "ordered_product_sales": sum((s.ordered_product_sales for s in store_summaries), Decimal("0")),
        "units_ordered": sum((Decimal(s.units_ordered) for s in store_summaries), Decimal("0")),
        "ad_spend": sum((s.ad_spend for s in store_summaries), Decimal("0")),
        "ad_sales": sum((s.ad_sales for s in store_summaries), Decimal("0")),
    }
    return DailyReportDocument(
        report_date=report_date,
        store_summaries=store_summaries,
        totals=totals,
        warnings=warnings,
    )
```

- [ ] **Step 4: Implement Markdown and Excel exporters**

Create `backend/app/services/reports/markdown.py`:

```python
from app.schemas.reports import DailyReportDocument


def render_daily_report_markdown(report: DailyReportDocument) -> str:
    lines = [
        f"# Daily Amazon Report - {report.report_date.isoformat()}",
        "",
        "## Executive Summary",
        f"- Ordered product sales: {report.totals.get('ordered_product_sales', 0)}",
        f"- Units ordered: {report.totals.get('units_ordered', 0)}",
        f"- Ad spend: {report.totals.get('ad_spend', 0)}",
        f"- Ad sales: {report.totals.get('ad_sales', 0)}",
        "",
        "## Store Summary",
    ]
    for store in report.store_summaries:
        lines.append(
            f"- {store.seller_name}: sales {store.ordered_product_sales}, units {store.units_ordered}, ACOS {store.acos}"
        )
    lines.extend(["", "## Data Freshness"])
    if report.warnings:
        lines.extend([f"- {warning}" for warning in report.warnings])
    else:
        lines.append("- No freshness warnings.")
    return "\n".join(lines) + "\n"
```

Create `backend/app/services/reports/excel.py`:

```python
from pathlib import Path

import pandas as pd

from app.schemas.reports import DailyReportDocument


def write_daily_report_excel(report: DailyReportDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [summary.model_dump(mode="json") for summary in report.store_summaries]
    totals = [{"metric": key, "value": str(value)} for key, value in report.totals.items()]
    warnings = [{"warning": warning} for warning in report.warnings]

    with pd.ExcelWriter(output_path, engine="xlsxwriter") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Store Summary", index=False)
        pd.DataFrame(totals).to_excel(writer, sheet_name="Totals", index=False)
        pd.DataFrame(warnings).to_excel(writer, sheet_name="Warnings", index=False)
```

- [ ] **Step 5: Run report tests**

Run:

```powershell
cd backend
python -m pytest tests/test_reports.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/schemas/reports.py backend/app/services/reports backend/tests/test_reports.py
git commit -m "feat: generate daily reports"
```

## Task 10: LLM Snapshot, Mock Provider, and Output Validator

**Files:**
- Create: `backend/app/services/llm/snapshot.py`
- Create: `backend/app/services/llm/provider.py`
- Create: `backend/app/services/llm/validator.py`
- Test: `backend/tests/test_llm.py`

- [ ] **Step 1: Write failing LLM tests**

Create `backend/tests/test_llm.py`:

```python
from datetime import date

from app.schemas.reports import DailyReportDocument
from app.services.llm.provider import MockLLMProvider
from app.services.llm.snapshot import build_llm_snapshot
from app.services.llm.validator import validate_llm_output


def test_build_llm_snapshot_uses_report_data() -> None:
    report = DailyReportDocument(report_date=date(2026, 5, 25), store_summaries=[], totals={}, warnings=[])

    snapshot = build_llm_snapshot(report)

    assert snapshot["report_date"] == "2026-05-25"
    assert snapshot["warnings"] == []


def test_mock_llm_provider_returns_valid_output() -> None:
    output = MockLLMProvider().analyze({"report_date": "2026-05-25", "warnings": []})

    validated = validate_llm_output(output, snapshot={"evidence_ids": ["report:2026-05-25"]})

    assert validated["summary"]
    assert validated["findings"][0]["human_review_required"] is True


def test_validator_rejects_automatic_operation_recommendation() -> None:
    output = {
        "summary": "Unsafe",
        "findings": [
            {
                "title": "Auto change bid",
                "evidence_refs": ["report:2026-05-25"],
                "possible_causes": ["High ACOS"],
                "recommended_human_actions": ["Automatically change bid to 0.5"],
                "risk_level": "high",
                "confidence": "medium",
                "human_review_required": True,
            }
        ],
    }

    try:
        validate_llm_output(output, snapshot={"evidence_ids": ["report:2026-05-25"]})
    except ValueError as exc:
        assert "automatic" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_llm.py -v
```

Expected: FAIL with missing LLM modules.

- [ ] **Step 3: Implement snapshot and mock provider**

Create `backend/app/services/llm/snapshot.py`:

```python
from app.schemas.reports import DailyReportDocument


def build_llm_snapshot(report: DailyReportDocument) -> dict[str, object]:
    return {
        "report_date": report.report_date.isoformat(),
        "totals": {key: str(value) for key, value in report.totals.items()},
        "store_summaries": [summary.model_dump(mode="json") for summary in report.store_summaries],
        "warnings": report.warnings,
        "evidence_ids": [f"report:{report.report_date.isoformat()}"],
    }
```

Create `backend/app/services/llm/provider.py`:

```python
from typing import Protocol


class LLMProvider(Protocol):
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        raise NotImplementedError


class MockLLMProvider:
    def analyze(self, snapshot: dict[str, object]) -> dict[str, object]:
        report_date = str(snapshot["report_date"])
        return {
            "summary": f"Daily report for {report_date} is ready for review.",
            "findings": [
                {
                    "title": "Review daily changes",
                    "evidence_refs": [f"report:{report_date}"],
                    "possible_causes": ["Imported report data changed from prior day"],
                    "recommended_human_actions": ["Review flagged stores before taking action"],
                    "risk_level": "medium",
                    "confidence": "medium",
                    "human_review_required": True,
                }
            ],
        }
```

- [ ] **Step 4: Implement LLM output validator**

Create `backend/app/services/llm/validator.py`:

```python
BLOCKED_ACTION_WORDS = (
    "automatically change",
    "auto change",
    "change bid",
    "change price",
    "edit listing",
    "pause campaign",
    "increase budget",
)


def validate_llm_output(output: dict[str, object], snapshot: dict[str, object]) -> dict[str, object]:
    if not isinstance(output.get("summary"), str) or not output["summary"]:
        raise ValueError("LLM output missing summary")
    findings = output.get("findings")
    if not isinstance(findings, list):
        raise ValueError("LLM output missing findings")

    evidence_ids = set(snapshot.get("evidence_ids", []))
    for finding in findings:
        if not isinstance(finding, dict):
            raise ValueError("Finding must be an object")
        refs = finding.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            raise ValueError("Finding missing evidence references")
        if any(ref not in evidence_ids for ref in refs):
            raise ValueError("Finding references evidence outside snapshot")
        actions = finding.get("recommended_human_actions")
        if not isinstance(actions, list) or not actions:
            raise ValueError("Finding missing recommended human actions")
        joined_actions = " ".join(str(action).lower() for action in actions)
        if any(blocked in joined_actions for blocked in BLOCKED_ACTION_WORDS):
            raise ValueError("LLM output includes automatic Amazon operation recommendation")
        if finding.get("human_review_required") is not True:
            raise ValueError("Finding must require human review")
    return output
```

- [ ] **Step 5: Run LLM tests**

Run:

```powershell
cd backend
python -m pytest tests/test_llm.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/services/llm backend/tests/test_llm.py
git commit -m "feat: validate llm report summaries"
```

## Task 11: Import API Endpoints

**Files:**
- Create: `backend/app/api/routes/imports.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_imports.py`

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_api_imports.py`:

```python
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def test_import_preview_endpoint_accepts_csv() -> None:
    client = TestClient(create_app())
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    with fixture.open("rb") as file:
        response = client.post(
            "/api/imports/preview",
            data={
                "report_type": "business_report",
                "date_range_start": "2026-05-25",
                "date_range_end": "2026-05-25",
            },
            files={"file": ("business_report.csv", file, "text/csv")},
        )

    assert response.status_code == 200
    assert response.json()["detected_schema_version"] == "business_report.v1"
```

- [ ] **Step 2: Run API test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_api_imports.py -v
```

Expected: FAIL with 404 for `/api/imports/preview`.

- [ ] **Step 3: Implement import route**

Create `backend/app/api/routes/imports.py`:

```python
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, UploadFile

from app.domain.enums import ReportType
from app.schemas.imports import ImportPreviewResponse
from app.services.imports.orchestrator import preview_manual_import

router = APIRouter(prefix="/imports", tags=["imports"])


@router.post("/preview", response_model=ImportPreviewResponse)
async def preview_import(
    report_type: ReportType = Form(...),
    date_range_start: date = Form(...),
    date_range_end: date = Form(...),
    file: UploadFile = File(...),
) -> ImportPreviewResponse:
    suffix = Path(file.filename or "upload.csv").suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)
    return preview_manual_import(
        file_path=tmp_path,
        report_type=report_type,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
    )
```

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router


def create_app() -> FastAPI:
    app = FastAPI(title="Amazon Daily Copilot")
    app.include_router(health_router, prefix="/api")
    app.include_router(imports_router, prefix="/api")
    return app


app = create_app()
```

- [ ] **Step 4: Run API import tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_imports.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Run all backend tests**

Run:

```powershell
cd backend
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/routes/imports.py backend/app/main.py backend/tests/test_api_imports.py
git commit -m "feat: add manual import preview api"
```

## Task 12: Internal Web Pages

**Files:**
- Create: `backend/app/web/routes.py`
- Create: `backend/app/web/templates/base.html`
- Create: `backend/app/web/templates/dashboard.html`
- Create: `backend/app/web/templates/imports.html`
- Create: `backend/app/web/templates/reports.html`
- Create: `backend/app/web/templates/settings.html`
- Create: `backend/app/web/static/app.css`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

- [ ] **Step 1: Add web route assertions**

Append to `backend/tests/test_health.py`:

```python
def test_internal_pages_render() -> None:
    client = TestClient(create_app())

    for path in ["/", "/imports", "/reports", "/settings"]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Amazon Daily Copilot" in response.text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_health.py::test_internal_pages_render -v
```

Expected: FAIL with 404 for internal pages.

- [ ] **Step 3: Implement web routes**

Create `backend/app/web/routes.py`:

```python
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="app/web/templates")
router = APIRouter()


@router.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "Dashboard"})


@router.get("/imports")
def imports_page(request: Request):
    return templates.TemplateResponse("imports.html", {"request": request, "title": "Data Import"})


@router.get("/reports")
def reports_page(request: Request):
    return templates.TemplateResponse("reports.html", {"request": request, "title": "Report Center"})


@router.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "title": "Settings"})
```

- [ ] **Step 4: Implement templates and CSS**

Create `backend/app/web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} - Amazon Daily Copilot</title>
    <link rel="stylesheet" href="/static/app.css">
  </head>
  <body>
    <aside>
      <strong>Amazon Daily Copilot</strong>
      <nav>
        <a href="/">Dashboard</a>
        <a href="/imports">Data Import</a>
        <a href="/reports">Report Center</a>
        <a href="/settings">Settings</a>
      </nav>
    </aside>
    <main>
      {% block content %}{% endblock %}
    </main>
  </body>
</html>
```

Create `backend/app/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Dashboard</h1>
<section>
  <h2>Latest Daily Report</h2>
  <p>No report has been generated in this environment.</p>
</section>
{% endblock %}
```

Create `backend/app/web/templates/imports.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Data Import</h1>
<form method="post" action="/api/imports/preview" enctype="multipart/form-data">
  <label>Report type <input name="report_type" value="business_report"></label>
  <label>Start date <input name="date_range_start" type="date"></label>
  <label>End date <input name="date_range_end" type="date"></label>
  <label>File <input name="file" type="file"></label>
  <button type="submit">Preview Import</button>
</form>
{% endblock %}
```

Create `backend/app/web/templates/reports.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Report Center</h1>
<p>Generated reports will appear here.</p>
{% endblock %}
```

Create `backend/app/web/templates/settings.html`:

```html
{% extends "base.html" %}
{% block content %}
<h1>Settings</h1>
<p>Seller accounts, marketplaces, LLM provider, and delivery settings will be configured here.</p>
{% endblock %}
```

Create `backend/app/web/static/app.css`:

```css
body {
  margin: 0;
  display: grid;
  grid-template-columns: 240px 1fr;
  min-height: 100vh;
  font-family: Arial, sans-serif;
  color: #17202a;
  background: #f6f7f9;
}

aside {
  background: #111827;
  color: #ffffff;
  padding: 24px;
}

nav {
  display: grid;
  gap: 8px;
  margin-top: 24px;
}

nav a {
  color: #ffffff;
  text-decoration: none;
  padding: 8px 0;
}

main {
  padding: 32px;
}

section,
form {
  max-width: 920px;
  background: #ffffff;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  padding: 20px;
}

label {
  display: grid;
  gap: 6px;
  margin-bottom: 12px;
}

input,
button {
  font: inherit;
  padding: 8px 10px;
}
```

- [ ] **Step 5: Register routes and static files**

Modify `backend/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes.health import router as health_router
from app.api.routes.imports import router as imports_router
from app.web.routes import router as web_router


def create_app() -> FastAPI:
    app = FastAPI(title="Amazon Daily Copilot")
    app.mount("/static", StaticFiles(directory="app/web/static"), name="static")
    app.include_router(health_router, prefix="/api")
    app.include_router(imports_router, prefix="/api")
    app.include_router(web_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run web tests**

Run:

```powershell
cd backend
python -m pytest tests/test_health.py -v
```

Expected: all health and web tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/web backend/app/main.py backend/tests/test_health.py
git commit -m "feat: add internal web pages"
```

## Task 13: Settings API and Seed Data

**Files:**
- Create: `backend/app/schemas/settings.py`
- Create: `backend/app/api/routes/settings.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_api_settings.py`

- [ ] **Step 1: Write failing settings API test**

Create `backend/tests/test_api_settings.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_default_marketplaces_endpoint_returns_americas_marketplaces() -> None:
    client = TestClient(create_app())

    response = client.get("/api/settings/default-marketplaces")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["marketplace_id"] == "ATVPDKIKX0DER"
    assert payload[0]["region"] == "americas"
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_api_settings.py -v
```

Expected: FAIL with 404.

- [ ] **Step 3: Implement settings schema and route**

Create `backend/app/schemas/settings.py`:

```python
from pydantic import BaseModel


class MarketplaceSeed(BaseModel):
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str
```

Create `backend/app/api/routes/settings.py`:

```python
from fastapi import APIRouter

from app.schemas.settings import MarketplaceSeed

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/default-marketplaces", response_model=list[MarketplaceSeed])
def default_marketplaces() -> list[MarketplaceSeed]:
    return [
        MarketplaceSeed(
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        ),
        MarketplaceSeed(
            marketplace_id="A2EUQ1WTGCTBG2",
            region="americas",
            country_code="CA",
            timezone="America/Toronto",
            currency_code="CAD",
        ),
        MarketplaceSeed(
            marketplace_id="A1AM78C64UM0Y8",
            region="americas",
            country_code="MX",
            timezone="America/Mexico_City",
            currency_code="MXN",
        ),
    ]
```

Modify `backend/app/main.py` imports and `create_app`:

```python
from app.api.routes.settings import router as settings_router
```

```python
app.include_router(settings_router, prefix="/api")
```

- [ ] **Step 4: Run settings API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_settings.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/schemas/settings.py backend/app/api/routes/settings.py backend/app/main.py backend/tests/test_api_settings.py
git commit -m "feat: add settings marketplace seeds"
```

## Task 14: API Readiness Document

**Files:**
- Create: `docs/api-readiness/amazon-api-readiness.md`
- Test: manual document review

- [ ] **Step 1: Create API readiness checklist**

Create `docs/api-readiness/amazon-api-readiness.md`:

```markdown
# Amazon API Readiness Checklist

## SP-API

- Create or confirm Amazon Developer profile.
- Decide private app path for internal company use.
- Configure Login With Amazon credentials.
- Configure AWS IAM role and policy for SP-API.
- Record callback URL for the internal app.
- Request roles needed for reports, catalog/listings, inventory, and orders summaries.
- Exclude restricted buyer PII roles from the MVP.
- Store refresh tokens outside source control.
- Map target report types to `report_type` values used by the MVP.
- Implement 401 and 403 handling as authorization-expired or permission-denied job errors.
- Implement 429 handling as rate-limited job errors with retry-after awareness.

## Amazon Ads API

- Apply for Amazon Ads API access.
- Record client id and client secret outside source control.
- Confirm profiles for each seller account and marketplace.
- Map Sponsored Products campaign, targeting, and search term reports to MVP report types.
- Implement asynchronous report creation, polling, download, and raw dataset creation.
- Route downloaded report files through the same normalization pipeline as manual uploads.

## Adapter Contract

Every API integration must create a `RawDataset` envelope with:

- seller_account_id
- marketplace_id
- region
- source
- report_type
- date_range_start
- date_range_end
- schema_version
- raw_file_path
- raw_file_checksum
- row_count
- data_status
- source_generated_at
- ingested_at
- import_job_id or sync_job_id

API adapters must not write directly to normalized or metrics tables.
```

- [ ] **Step 2: Review checklist against MVP spec**

Run:

```powershell
rg -n "SP-API|Ads API|RawDataset|buyer PII" docs/api-readiness/amazon-api-readiness.md
```

Expected: output includes SP-API, Ads API, RawDataset, and buyer PII checklist items.

- [ ] **Step 3: Commit**

```powershell
git add docs/api-readiness/amazon-api-readiness.md
git commit -m "docs: add amazon api readiness checklist"
```

## Task 15: Full Verification and Local Run

**Files:**
- Modify: none unless verification exposes defects

- [ ] **Step 1: Run formatting and lint checks**

Run:

```powershell
cd backend
python -m ruff check .
```

Expected: no lint failures.

- [ ] **Step 2: Run full test suite**

Run:

```powershell
cd backend
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Start local services**

Run:

```powershell
docker compose up -d postgres
```

Expected: PostgreSQL container starts and exposes port `5432`.

- [ ] **Step 4: Apply migrations**

Run:

```powershell
cd backend
python -m alembic upgrade head
```

Expected: migration completes without errors.

- [ ] **Step 5: Start app**

Run:

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Expected: server starts on `http://127.0.0.1:8000`.

- [ ] **Step 6: Verify endpoints**

Run in another shell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/settings/default-marketplaces
```

Expected: health returns `status: ok`; marketplaces return US, CA, and MX seeds.

- [ ] **Step 7: Commit verification fixes if any**

If verification required code changes, commit them with:

```powershell
git add backend docs
git commit -m "fix: resolve mvp verification issues"
```

If no files changed, do not create a commit.

## Self-Review

Spec coverage:

- Multiple internal seller accounts: covered by Tasks 3 and 13.
- Americas first with global-ready marketplace fields: covered by Tasks 2, 3, and 13.
- Manual report upload: covered by Tasks 4, 5, 6, and 11.
- API-ready adapter contract: covered by Tasks 4 and 14.
- Raw, normalized, metrics, report pipeline: covered by Tasks 3, 7, 8, and 9.
- Daily report formats: JSON and Markdown covered by Task 9; Excel covered by Task 9.
- LLM snapshot and validator: covered by Task 10.
- Internal UI pages: covered by Task 12.
- Security boundary excluding buyer PII and automatic operations: covered by Tasks 10 and 14.
- Testing strategy: each implementation task begins with failing tests and verification commands.

Placeholder scan:

- The plan contains no unresolved markers or unspecified implementation slots.
- SP-API and Ads API live integrations are explicitly excluded from this MVP and represented by stubs plus a readiness checklist.

Type consistency:

- `ReportType`, `DataSource`, and `DataStatus` enum values are used consistently across schemas, adapters, services, and tests.
- `RawDatasetEnvelope` fields match the MVP design contract.
- `DailyReportDocument` is shared by report, Markdown, Excel, and LLM snapshot services.
