# Amazon V5 SP-API AI Report Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V5 internal SP-API report sync pipeline, data cleaning path, LLM schema/prompt layer, Excel output, and usable store-selection pages.

**Architecture:** Keep `ImportJob` as the single ingestion record for both manual files and SP-API downloads. Add `SPAPISyncJob` only for the Amazon Reports API lifecycle, then route downloaded files through the existing RawDataset/RawReportRows/Normalized pipeline. Only `business_sales_traffic` is enabled in V5; other report types stay blocked until their parser and field contract are explicit.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, httpx MockTransport, pandas/xlsxwriter, Jinja templates, pytest, ruff.

---

## Scope Check

This plan implements the V5 spec at `docs/superpowers/specs/2026-05-29-amazon-v5-spapi-ai-report-design.md`.

V5 includes:

- Manual SP-API sync jobs.
- LWA refresh-token access-token exchange.
- Reports API create/get/document/download lifecycle.
- `GET_SALES_AND_TRAFFIC_REPORT` ingestion into existing business-report normalization.
- Versioned LLM prompts and structured output validation.
- Excel sheets for AI insights and source provenance.
- Store dropdowns in Import, Reports, Settings, and a new SP-API Sync page.
- README and API readiness corrections.

V5 excludes:

- Buyer PII.
- Automatic scheduled sync.
- SaaS or external seller OAuth callback.
- Amazon Ads API.
- Amazon write operations.
- Financial/FBA/Listings report execution beyond disabled registry entries.

## File Structure

Create:

- `backend/app/api/routes/spapi.py` - SP-API report type and sync job API routes.
- `backend/app/schemas/spapi.py` - request/response schemas for report types and sync jobs.
- `backend/app/services/amazon/report_types.py` - hard whitelist for V5 report types.
- `backend/app/services/amazon/reports_client.py` - Reports API HTTP client.
- `backend/app/services/amazon/report_downloads.py` - report document download helper.
- `backend/app/services/amazon/sync_jobs.py` - sync job state machine and orchestration.
- `backend/app/services/imports/spapi_ingestion.py` - converts downloaded SP-API report bytes into ImportJob/RawDataset.
- `backend/app/services/llm/output_schema.py` - Pydantic LLM output schema and validation.
- `backend/app/services/llm/prompt_registry.py` - prompt loading by version.
- `backend/app/services/llm/prompts/daily_report_v1/system.md` - system prompt.
- `backend/app/services/llm/prompts/daily_report_v1/user.md` - user prompt template.
- `backend/app/web/templates/spapi_sync.html` - SP-API Sync page.
- `backend/migrations/versions/20260529_0005_spapi_sync_jobs.py` - sync job migration.
- `backend/tests/fixtures/sales_and_traffic_report.json` - Amazon-like JSON fixture.
- `backend/tests/test_spapi_report_types.py`
- `backend/tests/test_amazon_reports_client.py`
- `backend/tests/test_spapi_ingestion.py`
- `backend/tests/test_api_spapi.py`
- `backend/tests/test_llm_v5.py`
- `backend/tests/test_report_excel_v5.py`
- `backend/tests/test_web_v5.py`

Modify:

- `backend/app/domain/enums.py` - sync job statuses and error codes.
- `backend/app/models/amazon.py` - add `SPAPISyncJob`.
- `backend/app/models/__init__.py` - export `SPAPISyncJob`.
- `backend/app/services/amazon/lwa.py` - add refresh-token exchange.
- `backend/app/core/config.py` - add SP-API base URL setting.
- `backend/app/main.py` - register `spapi` API route.
- `backend/app/services/imports/parser.py` - parse sales-and-traffic JSON files.
- `backend/app/services/imports/persistence.py` - extract shared import persistence for `manual_file` and `sp_api`.
- `backend/app/services/imports/schema_registry.py` - support SP-API business report rows.
- `backend/app/services/reports/generator.py` - run LLM analysis and persist output status.
- `backend/app/services/reports/excel.py` - add V5 sheets.
- `backend/app/services/reports/markdown.py` - include AI section when available.
- `backend/app/services/llm/openai_compatible.py` - load prompts and validate with schema.
- `backend/app/services/llm/provider.py` - update mock output to V5 schema.
- `backend/app/services/llm/snapshot.py` - add evidence-rich snapshot.
- `backend/app/web/routes.py` - route `/spapi-sync`.
- `backend/app/web/templates/base.html` - add SP-API Sync navigation.
- `backend/app/web/templates/imports.html` - store dropdown and JSON/fetch flow.
- `backend/app/web/templates/reports.html` - store dropdown and JSON/fetch flow.
- `backend/app/web/templates/settings.html` - seller/account lists and clearer authorization binding.
- `docs/api-readiness/amazon-api-readiness.md` - remove IAM/SigV4 as required items.
- `README.md` - document V5 sync and report generation.

---

### Task 1: Data Model, Migration, And Schemas

**Files:**
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/app/models/amazon.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/spapi.py`
- Create: `backend/migrations/versions/20260529_0005_spapi_sync_jobs.py`
- Test: `backend/tests/test_spapi_models.py`

- [ ] **Step 1: Write the failing model test**

Create `backend/tests/test_spapi_models.py`:

```python
from datetime import date

from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.domain.enums import SPAPISyncJobStatus
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount


def test_spapi_sync_job_model_persists_report_lifecycle_fields() -> None:
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
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="client-id",
            refresh_token_encrypted="encrypted",
            token_type="bearer",
            authorized_at=utc_now(),
            status="active",
        )
        sync_job = SPAPISyncJob(
            seller_account=seller,
            marketplace=marketplace,
            amazon_authorization=authorization,
            internal_report_type="business_sales_traffic",
            amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
            date_range_start=date(2026, 5, 20),
            date_range_end=date(2026, 5, 20),
            report_options_json='{"dateGranularity":"DAY","asinGranularity":"SKU"}',
            status=SPAPISyncJobStatus.DRAFT.value,
        )
        session.add(sync_job)
        session.commit()

        stored = session.get(SPAPISyncJob, sync_job.id)
        assert stored is not None
        assert stored.seller_account_id == seller.id
        assert stored.marketplace_id == marketplace.id
        assert stored.amazon_authorization_id == authorization.id
        assert stored.import_job_id is None
        assert stored.status == "draft"
        assert stored.amazon_report_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_models.py -q
```

Expected: FAIL because `SPAPISyncJobStatus` or `SPAPISyncJob` does not exist.

- [ ] **Step 3: Add enums**

Modify `backend/app/domain/enums.py`:

```python
class SPAPISyncJobStatus(StrEnum):
    DRAFT = "draft"
    REQUESTED = "requested"
    PROCESSING = "processing"
    DOWNLOAD_READY = "download_ready"
    DOWNLOADED = "downloaded"
    IMPORTED = "imported"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SPAPISyncJobErrorCode(StrEnum):
    MISSING_AUTHORIZATION = "missing_authorization"
    LWA_TOKEN_FAILED = "lwa_token_failed"
    PERMISSION_DENIED = "permission_denied"
    RATE_LIMITED = "rate_limited"
    AMAZON_REPORT_FAILED = "amazon_report_failed"
    DOWNLOAD_FAILED = "download_failed"
    PARSE_FAILED = "parse_failed"
    NORMALIZE_FAILED = "normalize_failed"
    DUPLICATE_DATASET = "duplicate_dataset"
    UNEXPECTED_ERROR = "unexpected_error"
```

- [ ] **Step 4: Add SQLAlchemy model**

Append to `backend/app/models/amazon.py`. Merge the imports with the existing imports so the file has `from datetime import date, datetime` and `from sqlalchemy import Date, DateTime, ForeignKey, String, Text`:

```python
class SPAPISyncJob(TimestampMixin, Base):
    __tablename__ = "spapi_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_account_id: Mapped[int] = mapped_column(ForeignKey("seller_accounts.id"), index=True)
    marketplace_id: Mapped[int] = mapped_column(ForeignKey("marketplaces.id"), index=True)
    amazon_authorization_id: Mapped[int] = mapped_column(
        ForeignKey("amazon_authorizations.id"), index=True
    )
    import_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_jobs.id"), nullable=True, index=True
    )
    internal_report_type: Mapped[str] = mapped_column(String(80), index=True)
    amazon_report_type: Mapped[str] = mapped_column(String(120), index=True)
    date_range_start: Mapped[date] = mapped_column(Date)
    date_range_end: Mapped[date] = mapped_column(Date)
    report_options_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(40), index=True)
    amazon_report_id: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    amazon_report_document_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    download_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    seller_account: Mapped["SellerAccount"] = relationship()
    marketplace = relationship("Marketplace")
    amazon_authorization: Mapped[AmazonAuthorization] = relationship()
    import_job = relationship("ImportJob")
```

Ensure imports in `backend/app/models/amazon.py` include `date`, `Integer` only if used, and `relationship` remains imported.

- [ ] **Step 5: Export model**

Modify `backend/app/models/__init__.py`:

```python
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
```

Add `"SPAPISyncJob"` to `__all__`.

- [ ] **Step 6: Add Pydantic schemas**

Create `backend/app/schemas/spapi.py`:

```python
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SPAPIReportTypeResponse(BaseModel):
    internal_report_type: str
    amazon_report_type: str
    display_name: str
    role_group: str
    source: str
    output_format: str
    parser_version: str
    normalizer_version: str
    status: str
    pii_risk: str
    notes: str


class SPAPISyncJobCreate(BaseModel):
    seller_account_id: int
    marketplace_id: int
    internal_report_type: str
    date_range_start: date
    date_range_end: date
    report_options: dict[str, Any] = Field(default_factory=dict)


class SPAPISyncJobResponse(BaseModel):
    id: int
    seller_account_id: int
    marketplace_id: int
    amazon_authorization_id: int
    import_job_id: int | None
    internal_report_type: str
    amazon_report_type: str
    date_range_start: date
    date_range_end: date
    status: str
    amazon_report_id: str | None
    amazon_report_document_id: str | None
    download_path: str | None
    error_code: str | None
    error_message: str | None
    requested_at: datetime | None
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 7: Add Alembic migration**

Create `backend/migrations/versions/20260529_0005_spapi_sync_jobs.py`:

```python
"""add spapi sync jobs

Revision ID: 20260529_0005
Revises: 20260529_0004
Create Date: 2026-05-29 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0005"
down_revision = "20260529_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "spapi_sync_jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("seller_account_id", sa.Integer(), nullable=False),
        sa.Column("marketplace_id", sa.Integer(), nullable=False),
        sa.Column("amazon_authorization_id", sa.Integer(), nullable=False),
        sa.Column("import_job_id", sa.Integer(), nullable=True),
        sa.Column("internal_report_type", sa.String(length=80), nullable=False),
        sa.Column("amazon_report_type", sa.String(length=120), nullable=False),
        sa.Column("date_range_start", sa.Date(), nullable=False),
        sa.Column("date_range_end", sa.Date(), nullable=False),
        sa.Column("report_options_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("amazon_report_id", sa.String(length=160), nullable=True),
        sa.Column("amazon_report_document_id", sa.String(length=160), nullable=True),
        sa.Column("download_path", sa.String(length=500), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["amazon_authorization_id"], ["amazon_authorizations.id"]),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"]),
        sa.ForeignKeyConstraint(["marketplace_id"], ["marketplaces.id"]),
        sa.ForeignKeyConstraint(["seller_account_id"], ["seller_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_spapi_sync_jobs_seller_account_id", "spapi_sync_jobs", ["seller_account_id"])
    op.create_index("ix_spapi_sync_jobs_marketplace_id", "spapi_sync_jobs", ["marketplace_id"])
    op.create_index(
        "ix_spapi_sync_jobs_amazon_authorization_id",
        "spapi_sync_jobs",
        ["amazon_authorization_id"],
    )
    op.create_index("ix_spapi_sync_jobs_import_job_id", "spapi_sync_jobs", ["import_job_id"])
    op.create_index("ix_spapi_sync_jobs_internal_report_type", "spapi_sync_jobs", ["internal_report_type"])
    op.create_index("ix_spapi_sync_jobs_amazon_report_type", "spapi_sync_jobs", ["amazon_report_type"])
    op.create_index("ix_spapi_sync_jobs_status", "spapi_sync_jobs", ["status"])
    op.create_index("ix_spapi_sync_jobs_amazon_report_id", "spapi_sync_jobs", ["amazon_report_id"])


def downgrade() -> None:
    op.drop_index("ix_spapi_sync_jobs_amazon_report_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_status", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_amazon_report_type", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_internal_report_type", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_import_job_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_amazon_authorization_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_marketplace_id", table_name="spapi_sync_jobs")
    op.drop_index("ix_spapi_sync_jobs_seller_account_id", table_name="spapi_sync_jobs")
    op.drop_table("spapi_sync_jobs")
```

- [ ] **Step 8: Run model test**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_models.py -q
```

Expected: PASS.

- [ ] **Step 9: Run migration smoke test**

Run:

```powershell
cd backend
python -m alembic upgrade head
```

Expected: migration reaches `20260529_0005`.

- [ ] **Step 10: Commit**

Run:

```powershell
git add backend/app/domain/enums.py backend/app/models/amazon.py backend/app/models/__init__.py backend/app/schemas/spapi.py backend/migrations/versions/20260529_0005_spapi_sync_jobs.py backend/tests/test_spapi_models.py
git commit -m "feat: add spapi sync job model"
```

---

### Task 2: Report Type Registry And API Route

**Files:**
- Create: `backend/app/services/amazon/report_types.py`
- Create: `backend/app/api/routes/spapi.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_spapi_report_types.py`
- Test: `backend/tests/test_api_spapi.py`

- [ ] **Step 1: Write registry tests**

Create `backend/tests/test_spapi_report_types.py`:

```python
from app.services.amazon.report_types import get_enabled_report_types, get_report_type


def test_enabled_report_types_only_exposes_business_sales_traffic() -> None:
    enabled = get_enabled_report_types()

    assert [item.internal_report_type for item in enabled] == ["business_sales_traffic"]
    assert enabled[0].amazon_report_type == "GET_SALES_AND_TRAFFIC_REPORT"
    assert enabled[0].role_group == "品牌分析"
    assert enabled[0].pii_risk == "none"


def test_disabled_report_type_is_not_returned_as_enabled() -> None:
    open_listings = get_report_type("open_listings")

    assert open_listings.status == "disabled"
    assert all(item.internal_report_type != "open_listings" for item in get_enabled_report_types())
```

- [ ] **Step 2: Write API route test**

Append to `backend/tests/test_api_spapi.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_report_types_endpoint_returns_only_enabled_types() -> None:
    client = TestClient(create_app())

    response = client.get("/api/spapi/report-types")

    assert response.status_code == 200
    payload = response.json()
    assert [item["internal_report_type"] for item in payload] == ["business_sales_traffic"]
    assert "open_listings" not in response.text
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_report_types.py tests/test_api_spapi.py -q
```

Expected: FAIL because registry and route do not exist.

- [ ] **Step 4: Implement registry**

Create `backend/app/services/amazon/report_types.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SPAPIReportType:
    internal_report_type: str
    amazon_report_type: str
    display_name: str
    role_group: str
    source: str
    output_format: str
    parser_version: str
    normalizer_version: str
    status: str
    pii_risk: str
    notes: str


REPORT_TYPES = {
    "business_sales_traffic": SPAPIReportType(
        internal_report_type="business_sales_traffic",
        amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
        display_name="销售与流量业务报表",
        role_group="品牌分析",
        source="sp_api_reports",
        output_format="json",
        parser_version="sales_and_traffic.v1",
        normalizer_version="business_report.v1",
        status="enabled",
        pii_risk="none",
        notes="V5 first supported SP-API report. Does not include buyer PII.",
    ),
    "open_listings": SPAPIReportType(
        internal_report_type="open_listings",
        amazon_report_type="GET_FLAT_FILE_OPEN_LISTINGS_DATA",
        display_name="当前在售 Listing",
        role_group="商品信息/定价/库存和订单追踪",
        source="sp_api_reports",
        output_format="tsv",
        parser_version="open_listings.v1",
        normalizer_version="inventory_report.v1",
        status="disabled",
        pii_risk="none",
        notes="Registered but blocked until parser and normalization are implemented.",
    ),
    "all_listings": SPAPIReportType(
        internal_report_type="all_listings",
        amazon_report_type="GET_MERCHANT_LISTINGS_ALL_DATA",
        display_name="全部 Listing",
        role_group="商品信息/定价/库存和订单追踪",
        source="sp_api_reports",
        output_format="tsv",
        parser_version="all_listings.v1",
        normalizer_version="inventory_report.v1",
        status="disabled",
        pii_risk="none",
        notes="Registered but blocked until parser and normalization are implemented.",
    ),
}


class ReportTypeNotFoundError(Exception):
    pass


class ReportTypeDisabledError(Exception):
    pass


def list_report_types() -> list[SPAPIReportType]:
    return list(REPORT_TYPES.values())


def get_enabled_report_types() -> list[SPAPIReportType]:
    return [item for item in REPORT_TYPES.values() if item.status == "enabled"]


def get_report_type(internal_report_type: str) -> SPAPIReportType:
    try:
        return REPORT_TYPES[internal_report_type]
    except KeyError as exc:
        raise ReportTypeNotFoundError(f"SP-API report type not found: {internal_report_type}") from exc


def require_enabled_report_type(internal_report_type: str) -> SPAPIReportType:
    report_type = get_report_type(internal_report_type)
    if report_type.status != "enabled":
        raise ReportTypeDisabledError(f"SP-API report type is disabled: {internal_report_type}")
    return report_type
```

- [ ] **Step 5: Add route**

Create `backend/app/api/routes/spapi.py`:

```python
from fastapi import APIRouter

from app.schemas.spapi import SPAPIReportTypeResponse
from app.services.amazon.report_types import get_enabled_report_types

router = APIRouter(prefix="/spapi", tags=["spapi"])


@router.get("/report-types", response_model=list[SPAPIReportTypeResponse])
def report_types() -> list[SPAPIReportTypeResponse]:
    return [
        SPAPIReportTypeResponse(**report_type.__dict__)
        for report_type in get_enabled_report_types()
    ]
```

- [ ] **Step 6: Register route**

Modify `backend/app/main.py`:

```python
from app.api.routes.spapi import router as spapi_router
```

Then include:

```python
app.include_router(spapi_router, prefix="/api")
```

- [ ] **Step 7: Run tests**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_report_types.py tests/test_api_spapi.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/app/services/amazon/report_types.py backend/app/api/routes/spapi.py backend/app/main.py backend/tests/test_spapi_report_types.py backend/tests/test_api_spapi.py
git commit -m "feat: add spapi report type registry"
```

---

### Task 3: LWA Refresh Token Exchange And Reports API Client

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/amazon/lwa.py`
- Create: `backend/app/services/amazon/reports_client.py`
- Create: `backend/app/services/amazon/report_downloads.py`
- Test: `backend/tests/test_amazon_lwa.py`
- Test: `backend/tests/test_amazon_reports_client.py`

- [ ] **Step 1: Add LWA refresh-token test**

Append to `backend/tests/test_amazon_lwa.py`:

```python
import httpx

from app.services.amazon.lwa import LWAClient


def test_lwa_client_exchanges_refresh_token_for_access_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://api.amazon.com/auth/o2/token"
        assert b"grant_type=refresh_token" in request.content
        assert b"refresh_token=Atzr%7Cexample" in request.content
        return httpx.Response(
            200,
            json={
                "access_token": "access-token",
                "token_type": "bearer",
                "expires_in": 3600,
            },
        )

    client = LWAClient(
        token_url="https://api.amazon.com/auth/o2/token",
        client_id="client-id",
        client_secret="client-secret",
        transport=httpx.MockTransport(handler),
    )

    result = client.exchange_refresh_token(refresh_token="Atzr|example")

    assert result.access_token == "access-token"
    assert result.token_type == "bearer"
    assert result.expires_in == 3600
```

- [ ] **Step 2: Add Reports client tests**

Create `backend/tests/test_amazon_reports_client.py`:

```python
from datetime import date

import httpx

from app.services.amazon.reports_client import AmazonReportsClient


def test_reports_client_creates_report() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://sellingpartnerapi-na.amazon.com/reports/2021-06-30/reports"
        assert request.headers["x-amz-access-token"] == "access-token"
        payload = request.read().decode()
        assert "GET_SALES_AND_TRAFFIC_REPORT" in payload
        assert "ATVPDKIKX0DER" in payload
        return httpx.Response(202, json={"reportId": "report-1"})

    client = AmazonReportsClient(
        base_url="https://sellingpartnerapi-na.amazon.com",
        transport=httpx.MockTransport(handler),
    )

    report_id = client.create_report(
        access_token="access-token",
        amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
        marketplace_ids=["ATVPDKIKX0DER"],
        date_range_start=date(2026, 5, 20),
        date_range_end=date(2026, 5, 20),
        report_options={"dateGranularity": "DAY", "asinGranularity": "SKU"},
    )

    assert report_id == "report-1"


def test_reports_client_maps_403_to_permission_denied() -> None:
    client = AmazonReportsClient(
        base_url="https://sellingpartnerapi-na.amazon.com",
        transport=httpx.MockTransport(lambda _request: httpx.Response(403, text="denied")),
    )

    try:
        client.get_report(access_token="access-token", report_id="report-1")
    except PermissionError as exc:
        assert "permission denied" in str(exc).lower()
    else:
        raise AssertionError("Expected PermissionError")
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_lwa.py tests/test_amazon_reports_client.py -q
```

Expected: FAIL because refresh exchange and reports client do not exist.

- [ ] **Step 4: Add config**

Modify `backend/app/core/config.py`:

```python
AMAZON_SPAPI_BASE_URL: str = "https://sellingpartnerapi-na.amazon.com"
AMAZON_REPORTS_TIMEOUT_SECONDS: int = 30
```

- [ ] **Step 5: Add LWA access-token response and method**

Modify `backend/app/services/amazon/lwa.py`:

```python
@dataclass(frozen=True)
class LWAAccessTokenResponse:
    access_token: str
    token_type: str | None
    expires_in: int | None
```

Add method:

```python
def exchange_refresh_token(self, *, refresh_token: str) -> LWAAccessTokenResponse:
    try:
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        raise LWATokenExchangeError(f"LWA refresh token exchange failed: {exc}") from exc

    access_token = payload.get("access_token")
    if not access_token:
        raise LWATokenExchangeError("LWA token response did not include access_token")

    return LWAAccessTokenResponse(
        access_token=access_token,
        token_type=payload.get("token_type"),
        expires_in=payload.get("expires_in"),
    )
```

- [ ] **Step 6: Implement Reports client**

Create `backend/app/services/amazon/reports_client.py`:

```python
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx


class AmazonReportsRateLimitError(Exception):
    def __init__(self, retry_after: str | None) -> None:
        super().__init__("Amazon Reports API rate limited the request")
        self.retry_after = retry_after


class AmazonReportsAPIError(Exception):
    pass


@dataclass(frozen=True)
class AmazonReportStatus:
    report_id: str
    processing_status: str
    report_document_id: str | None


@dataclass(frozen=True)
class AmazonReportDocument:
    report_document_id: str
    url: str
    compression_algorithm: str | None


class AmazonReportsClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    def create_report(
        self,
        *,
        access_token: str,
        amazon_report_type: str,
        marketplace_ids: list[str],
        date_range_start: date,
        date_range_end: date,
        report_options: dict[str, Any],
    ) -> str:
        payload = {
            "reportType": amazon_report_type,
            "marketplaceIds": marketplace_ids,
            "dataStartTime": f"{date_range_start.isoformat()}T00:00:00Z",
            "dataEndTime": f"{date_range_end.isoformat()}T23:59:59Z",
            "reportOptions": report_options,
        }
        response = self._request(
            "POST",
            "/reports/2021-06-30/reports",
            access_token=access_token,
            json=payload,
        )
        report_id = response.json().get("reportId")
        if not report_id:
            raise AmazonReportsAPIError("Amazon createReport response did not include reportId")
        return str(report_id)

    def get_report(self, *, access_token: str, report_id: str) -> AmazonReportStatus:
        response = self._request(
            "GET",
            f"/reports/2021-06-30/reports/{report_id}",
            access_token=access_token,
        )
        payload = response.json()
        return AmazonReportStatus(
            report_id=str(payload.get("reportId") or report_id),
            processing_status=str(payload.get("processingStatus") or ""),
            report_document_id=payload.get("reportDocumentId"),
        )

    def get_report_document(
        self,
        *,
        access_token: str,
        report_document_id: str,
    ) -> AmazonReportDocument:
        response = self._request(
            "GET",
            f"/reports/2021-06-30/documents/{report_document_id}",
            access_token=access_token,
        )
        payload = response.json()
        url = payload.get("url")
        if not url:
            raise AmazonReportsAPIError("Amazon getReportDocument response did not include url")
        return AmazonReportDocument(
            report_document_id=str(payload.get("reportDocumentId") or report_document_id),
            url=str(url),
            compression_algorithm=payload.get("compressionAlgorithm"),
        )

    def _request(self, method: str, path: str, *, access_token: str, **kwargs: Any) -> httpx.Response:
        with httpx.Client(timeout=self.timeout_seconds, transport=self.transport) as client:
            response = client.request(
                method,
                f"{self.base_url}{path}",
                headers={"x-amz-access-token": access_token},
                **kwargs,
            )
        if response.status_code in {401, 403}:
            raise PermissionError("Amazon Reports API permission denied")
        if response.status_code == 429:
            raise AmazonReportsRateLimitError(response.headers.get("retry-after"))
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AmazonReportsAPIError(str(exc)) from exc
        return response
```

- [ ] **Step 7: Implement download helper**

Create `backend/app/services/amazon/report_downloads.py`:

```python
import gzip
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class DownloadedReportDocument:
    content: bytes
    filename: str


class AmazonReportDownloadError(Exception):
    pass


def download_report_document(
    *,
    url: str,
    report_document_id: str,
    compression_algorithm: str | None,
    timeout_seconds: int = 30,
    transport: httpx.BaseTransport | None = None,
) -> DownloadedReportDocument:
    try:
        with httpx.Client(timeout=timeout_seconds, transport=transport) as client:
            response = client.get(url)
            response.raise_for_status()
        content = response.content
        if compression_algorithm == "GZIP":
            content = gzip.decompress(content)
    except Exception as exc:
        raise AmazonReportDownloadError(f"Amazon report document download failed: {exc}") from exc

    return DownloadedReportDocument(
        content=content,
        filename=f"{report_document_id}.json",
    )
```

- [ ] **Step 8: Run tests**

Run:

```powershell
cd backend
python -m pytest tests/test_amazon_lwa.py tests/test_amazon_reports_client.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

Run:

```powershell
git add backend/app/core/config.py backend/app/services/amazon/lwa.py backend/app/services/amazon/reports_client.py backend/app/services/amazon/report_downloads.py backend/tests/test_amazon_lwa.py backend/tests/test_amazon_reports_client.py
git commit -m "feat: add amazon reports client"
```

---

### Task 4: SP-API Ingestion For Sales And Traffic Report

**Files:**
- Create: `backend/tests/fixtures/sales_and_traffic_report.json`
- Modify: `backend/app/services/imports/parser.py`
- Modify: `backend/app/services/imports/schema_registry.py`
- Modify: `backend/app/services/imports/persistence.py`
- Create: `backend/app/services/imports/spapi_ingestion.py`
- Test: `backend/tests/test_spapi_ingestion.py`

- [ ] **Step 1: Add Amazon-like JSON fixture**

Create `backend/tests/fixtures/sales_and_traffic_report.json`:

```json
{
  "reportSpecification": {
    "reportType": "GET_SALES_AND_TRAFFIC_REPORT",
    "marketplaceIds": ["ATVPDKIKX0DER"]
  },
  "salesAndTrafficByAsin": [
    {
      "parentAsin": "B0PARENT",
      "childAsin": "B0TESTASIN",
      "sku": "SKU-1",
      "salesByAsin": {
        "orderedProductSales": {"amount": 125.50, "currencyCode": "USD"},
        "unitsOrdered": 5
      },
      "trafficByAsin": {
        "sessions": 80,
        "pageViews": 120,
        "buyBoxPercentage": 95.0
      }
    }
  ],
  "salesAndTrafficByDate": [
    {
      "date": "2026-05-20",
      "salesByDate": {
        "orderedProductSales": {"amount": 125.50, "currencyCode": "USD"},
        "unitsOrdered": 5
      },
      "trafficByDate": {
        "sessions": 80,
        "pageViews": 120,
        "buyBoxPercentage": 95.0
      }
    }
  ]
}
```

- [ ] **Step 2: Write ingestion test**

Create `backend/tests/test_spapi_ingestion.py`:

```python
from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset
from app.models.normalized import NormalizedBusinessDaily
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.imports.spapi_ingestion import confirm_spapi_report_import


def test_confirm_spapi_report_import_persists_raw_and_normalized_rows(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "sales_and_traffic_report.json"

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        session.add(marketplace)
        session.flush()

        response = confirm_spapi_report_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            internal_report_type="business_sales_traffic",
            amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
            date_range_start=date(2026, 5, 20),
            date_range_end=date(2026, 5, 20),
            original_filename="sales-and-traffic.json",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert response.report_type == "business_report"
        assert session.query(ImportJob).one().source == "sp_api"
        assert session.query(RawDataset).one().source == "sp_api"
        row = session.query(NormalizedBusinessDaily).one()
        assert row.report_date == date(2026, 5, 20)
        assert row.sku == "SKU-1"
        assert row.asin == "B0TESTASIN"
        assert str(row.ordered_product_sales) == "125.50"
        assert row.units_ordered == 5
```

- [ ] **Step 3: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_ingestion.py -q
```

Expected: FAIL because `confirm_spapi_report_import` and JSON parser support do not exist.

- [ ] **Step 4: Add JSON parser support**

Modify `backend/app/services/imports/parser.py`:

```python
import json
```

Inside `parse_report_file`, add:

```python
elif suffix == ".json":
    return _parse_sales_and_traffic_json(path)
```

Add helper:

```python
def _parse_sales_and_traffic_json(path: Path) -> ParsedReportFile:
    payload = json.loads(path.read_text(encoding="utf-8"))
    date_rows = payload.get("salesAndTrafficByDate") or []
    asin_rows = payload.get("salesAndTrafficByAsin") or []
    report_date = str(date_rows[0].get("date")) if date_rows else ""
    rows: list[dict[str, str]] = []
    for item in asin_rows:
        sales = item.get("salesByAsin") or {}
        traffic = item.get("trafficByAsin") or {}
        amount = (sales.get("orderedProductSales") or {}).get("amount") or "0"
        rows.append(
            {
                "Date": report_date,
                "ASIN": str(item.get("childAsin") or item.get("parentAsin") or ""),
                "SKU": str(item.get("sku") or ""),
                "Sessions": str(traffic.get("sessions") or 0),
                "Page Views": str(traffic.get("pageViews") or 0),
                "Units Ordered": str(sales.get("unitsOrdered") or 0),
                "Ordered Product Sales": str(amount),
                "Conversion Rate": str(traffic.get("unitSessionPercentage") or ""),
                "Buy Box Percentage": str(traffic.get("buyBoxPercentage") or ""),
            }
        )
    headers = [
        "Date",
        "ASIN",
        "SKU",
        "Sessions",
        "Page Views",
        "Units Ordered",
        "Ordered Product Sales",
        "Conversion Rate",
        "Buy Box Percentage",
    ]
    return ParsedReportFile(headers=headers, rows=rows, row_count=len(rows), sample_rows=rows[:5])
```

- [ ] **Step 5: Extract shared persistence**

Modify `backend/app/services/imports/persistence.py` so `confirm_manual_import()` calls a shared function:

```python
def persist_imported_report(
    *,
    session: Session,
    storage: LocalStorageBackend,
    seller_account_id: int,
    marketplace_id: int,
    source: DataSource,
    report_type: ReportType,
    date_range_start: date,
    date_range_end: date,
    original_filename: str,
    file_bytes: bytes,
) -> ImportConfirmResponse:
    ...
```

The body is the current `confirm_manual_import` body with these exact replacements:

- `source=source.value` for both `ImportJob` and `RawDataset`.
- The duplicate check remains on seller, marketplace, report type, and checksum.
- `data_version=f"{source.value}:{report_type.value}:{date_range_end.isoformat()}:{stored_file.checksum[:12]}"`.

Then make `confirm_manual_import()` return:

```python
return persist_imported_report(
    session=session,
    storage=storage,
    seller_account_id=seller_account_id,
    marketplace_id=marketplace_id,
    source=DataSource.MANUAL_FILE,
    report_type=report_type,
    date_range_start=date_range_start,
    date_range_end=date_range_end,
    original_filename=original_filename,
    file_bytes=file_bytes,
)
```

- [ ] **Step 6: Add SP-API ingestion wrapper**

Create `backend/app/services/imports/spapi_ingestion.py`:

```python
from datetime import date

from sqlalchemy.orm import Session

from app.core.storage import LocalStorageBackend
from app.domain.enums import DataSource, ReportType
from app.schemas.imports import ImportConfirmResponse
from app.services.imports.persistence import persist_imported_report


class UnsupportedSPAPIReportTypeError(Exception):
    pass


def confirm_spapi_report_import(
    *,
    session: Session,
    storage: LocalStorageBackend,
    seller_account_id: int,
    marketplace_id: int,
    internal_report_type: str,
    amazon_report_type: str,
    date_range_start: date,
    date_range_end: date,
    original_filename: str,
    file_bytes: bytes,
) -> ImportConfirmResponse:
    if internal_report_type != "business_sales_traffic":
        raise UnsupportedSPAPIReportTypeError(
            f"Unsupported SP-API report type: {internal_report_type}"
        )
    if amazon_report_type != "GET_SALES_AND_TRAFFIC_REPORT":
        raise UnsupportedSPAPIReportTypeError(
            f"Unsupported Amazon report type: {amazon_report_type}"
        )

    return persist_imported_report(
        session=session,
        storage=storage,
        seller_account_id=seller_account_id,
        marketplace_id=marketplace_id,
        source=DataSource.SP_API,
        report_type=ReportType.BUSINESS_REPORT,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        original_filename=original_filename,
        file_bytes=file_bytes,
    )
```

- [ ] **Step 7: Run import and regression tests**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_ingestion.py tests/test_import_confirm.py tests/test_api_imports.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/tests/fixtures/sales_and_traffic_report.json backend/app/services/imports/parser.py backend/app/services/imports/persistence.py backend/app/services/imports/spapi_ingestion.py backend/tests/test_spapi_ingestion.py
git commit -m "feat: ingest spapi sales traffic reports"
```

---

### Task 5: Sync Job State Machine And API

**Files:**
- Create: `backend/app/services/amazon/sync_jobs.py`
- Modify: `backend/app/api/routes/spapi.py`
- Test: `backend/tests/test_api_spapi.py`

- [ ] **Step 1: Add API sync job tests**

Append to `backend/tests/test_api_spapi.py`:

```python
from collections.abc import Generator
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_session, get_settings
from app.core.config import Settings
from app.core.db import create_session_factory, create_sync_engine
from app.core.time import utc_now
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount


def make_db_client() -> tuple[TestClient, sessionmaker[Session]]:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    app = create_app()

    def override_session() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    def override_settings() -> Settings:
        return Settings(
            DATABASE_URL="sqlite+pysqlite:///:memory:",
            AMAZON_LWA_CLIENT_ID="client-id",
            AMAZON_LWA_CLIENT_SECRET="client-secret",
            TOKEN_ENCRYPTION_KEY="MDEyMzQ1Njc4OUFCQ0RFRjAxMjM0NTY3ODlBQkNERUY=",
        )

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_settings] = override_settings
    return TestClient(app), session_factory


def seed_store_with_authorization(session: Session) -> tuple[SellerAccount, Marketplace]:
    org = Organization(name="Internal Team", slug="internal")
    seller = SellerAccount(
        organization=org,
        display_name="US Store",
        amazon_seller_id="A3FHEXAMPLEYWS",
    )
    marketplace = Marketplace(
        seller_account=seller,
        marketplace_id="ATVPDKIKX0DER",
        region="americas",
        country_code="US",
        timezone="America/Los_Angeles",
        currency_code="USD",
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
    session.flush()
    return seller, marketplace


def test_create_sync_job_uses_enabled_report_type_and_authorization() -> None:
    client, session_factory = make_db_client()
    with session_factory() as session:
        seller, marketplace = seed_store_with_authorization(session)
        session.commit()
        seller_id = seller.id
        marketplace_id = marketplace.id

    response = client.post(
        "/api/spapi/sync-jobs",
        json={
            "seller_account_id": seller_id,
            "marketplace_id": marketplace_id,
            "internal_report_type": "business_sales_traffic",
            "date_range_start": "2026-05-20",
            "date_range_end": "2026-05-20",
            "report_options": {},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "draft"
    assert payload["amazon_report_type"] == "GET_SALES_AND_TRAFFIC_REPORT"

    with session_factory() as session:
        stored = session.query(SPAPISyncJob).one()
        assert stored.report_options_json == '{"dateGranularity":"DAY","asinGranularity":"SKU"}'


def test_create_sync_job_rejects_disabled_report_type() -> None:
    client, session_factory = make_db_client()
    with session_factory() as session:
        seller, marketplace = seed_store_with_authorization(session)
        session.commit()
        seller_id = seller.id
        marketplace_id = marketplace.id

    response = client.post(
        "/api/spapi/sync-jobs",
        json={
            "seller_account_id": seller_id,
            "marketplace_id": marketplace_id,
            "internal_report_type": "open_listings",
            "date_range_start": "2026-05-20",
            "date_range_end": "2026-05-20",
            "report_options": {},
        },
    )

    assert response.status_code == 400
    assert "disabled" in response.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_api_spapi.py -q
```

Expected: FAIL because sync job service and endpoints do not exist.

- [ ] **Step 3: Implement sync job creation and listing**

Create `backend/app/services/amazon/sync_jobs.py` with creation/listing functions:

```python
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import AmazonAuthorizationStatus, SPAPISyncJobStatus
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.settings import Marketplace, SellerAccount
from app.services.amazon.report_types import ReportTypeDisabledError, require_enabled_report_type


class SPAPISyncJobError(Exception):
    pass


def create_sync_job(
    *,
    session: Session,
    seller_account_id: int,
    marketplace_id: int,
    internal_report_type: str,
    date_range_start: date,
    date_range_end: date,
    report_options: dict[str, object],
) -> SPAPISyncJob:
    seller = session.get(SellerAccount, seller_account_id)
    marketplace = session.get(Marketplace, marketplace_id)
    if seller is None:
        raise SPAPISyncJobError("seller account not found")
    if marketplace is None or marketplace.seller_account_id != seller.id:
        raise SPAPISyncJobError("marketplace not found")
    if date_range_start > date_range_end:
        raise SPAPISyncJobError("date_range_start cannot be after date_range_end")
    try:
        report_type = require_enabled_report_type(internal_report_type)
    except ReportTypeDisabledError as exc:
        raise SPAPISyncJobError(str(exc)) from exc

    authorization = session.scalar(
        select(AmazonAuthorization).where(
            AmazonAuthorization.seller_account_id == seller.id,
            AmazonAuthorization.status == AmazonAuthorizationStatus.ACTIVE.value,
        )
    )
    if authorization is None:
        raise SPAPISyncJobError("active Amazon authorization not found")

    normalized_options = {
        "dateGranularity": str(report_options.get("dateGranularity") or "DAY"),
        "asinGranularity": str(report_options.get("asinGranularity") or "SKU"),
    }
    sync_job = SPAPISyncJob(
        seller_account=seller,
        marketplace=marketplace,
        amazon_authorization=authorization,
        internal_report_type=report_type.internal_report_type,
        amazon_report_type=report_type.amazon_report_type,
        date_range_start=date_range_start,
        date_range_end=date_range_end,
        report_options_json=json.dumps(normalized_options, separators=(",", ":")),
        status=SPAPISyncJobStatus.DRAFT.value,
    )
    session.add(sync_job)
    session.flush()
    return sync_job


def list_sync_jobs(session: Session) -> list[SPAPISyncJob]:
    return list(session.scalars(select(SPAPISyncJob).order_by(SPAPISyncJob.created_at.desc())))
```

- [ ] **Step 4: Wire endpoints**

Modify `backend/app/api/routes/spapi.py`:

```python
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.spapi import SPAPISyncJobCreate, SPAPISyncJobResponse
from app.services.amazon.sync_jobs import SPAPISyncJobError, create_sync_job, list_sync_jobs

SessionDep = Annotated[Session, Depends(get_session)]
```

Add routes:

```python
@router.get("/sync-jobs", response_model=list[SPAPISyncJobResponse])
def get_sync_jobs(session: SessionDep) -> list[SPAPISyncJobResponse]:
    return list_sync_jobs(session)


@router.post("/sync-jobs", response_model=SPAPISyncJobResponse)
def post_sync_job(payload: SPAPISyncJobCreate, session: SessionDep) -> SPAPISyncJobResponse:
    try:
        sync_job = create_sync_job(
            session=session,
            seller_account_id=payload.seller_account_id,
            marketplace_id=payload.marketplace_id,
            internal_report_type=payload.internal_report_type,
            date_range_start=payload.date_range_start,
            date_range_end=payload.date_range_end,
            report_options=payload.report_options,
        )
    except SPAPISyncJobError as exc:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session.commit()
    return sync_job
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_spapi.py -q
```

Expected: PASS for report type and create/list tests.

- [ ] **Step 6: Commit**

Run:

```powershell
git add backend/app/services/amazon/sync_jobs.py backend/app/api/routes/spapi.py backend/tests/test_api_spapi.py
git commit -m "feat: add spapi sync job api"
```

---

### Task 6: Run And Refresh Sync Jobs

**Files:**
- Modify: `backend/app/services/amazon/sync_jobs.py`
- Modify: `backend/app/api/routes/spapi.py`
- Test: `backend/tests/test_api_spapi.py`

- [ ] **Step 1: Add service-level tests using fakes**

Create or extend `backend/tests/test_spapi_sync_jobs.py`:

```python
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.core.time import utc_now
from app.models.amazon import AmazonAuthorization, SPAPISyncJob
from app.models.base import Base
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.amazon.reports_client import AmazonReportDocument, AmazonReportStatus
from app.services.amazon.sync_jobs import refresh_sync_job, run_sync_job


@dataclass
class FakeAccessToken:
    access_token: str = "access-token"
    token_type: str = "bearer"
    expires_in: int = 3600


class FakeLWAClient:
    def exchange_refresh_token(self, *, refresh_token: str) -> FakeAccessToken:
        assert refresh_token == "refresh-token"
        return FakeAccessToken()


class FakeReportsClient:
    def create_report(self, **kwargs) -> str:
        assert kwargs["access_token"] == "access-token"
        assert kwargs["amazon_report_type"] == "GET_SALES_AND_TRAFFIC_REPORT"
        return "report-1"

    def get_report(self, *, access_token: str, report_id: str) -> AmazonReportStatus:
        assert access_token == "access-token"
        assert report_id == "report-1"
        return AmazonReportStatus(
            report_id="report-1",
            processing_status="DONE",
            report_document_id="document-1",
        )

    def get_report_document(self, *, access_token: str, report_document_id: str) -> AmazonReportDocument:
        assert access_token == "access-token"
        assert report_document_id == "document-1"
        return AmazonReportDocument(
            report_document_id="document-1",
            url="https://download.example.test/document-1",
            compression_algorithm=None,
        )


def test_run_and_refresh_sync_job_imports_downloaded_report(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    content = (Path(__file__).parent / "fixtures" / "sales_and_traffic_report.json").read_bytes()

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="US Store",
            amazon_seller_id="A3FHEXAMPLEYWS",
        )
        marketplace = Marketplace(
            seller_account=seller,
            marketplace_id="ATVPDKIKX0DER",
            region="americas",
            country_code="US",
            timezone="America/Los_Angeles",
            currency_code="USD",
        )
        authorization = AmazonAuthorization(
            selling_partner_id="A3FHEXAMPLEYWS",
            seller_account=seller,
            lwa_client_id="client-id",
            refresh_token_encrypted="refresh-token",
            token_type="bearer",
            authorized_at=utc_now(),
            status="active",
        )
        sync_job = SPAPISyncJob(
            seller_account=seller,
            marketplace=marketplace,
            amazon_authorization=authorization,
            internal_report_type="business_sales_traffic",
            amazon_report_type="GET_SALES_AND_TRAFFIC_REPORT",
            date_range_start=date(2026, 5, 20),
            date_range_end=date(2026, 5, 20),
            report_options_json=json.dumps({"dateGranularity": "DAY", "asinGranularity": "SKU"}),
            status="draft",
        )
        session.add(sync_job)
        session.flush()

        run_sync_job(
            session=session,
            sync_job_id=sync_job.id,
            refresh_token_plaintext="refresh-token",
            lwa_client=FakeLWAClient(),
            reports_client=FakeReportsClient(),
        )
        assert sync_job.status == "requested"
        assert sync_job.amazon_report_id == "report-1"

        refresh_sync_job(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            sync_job_id=sync_job.id,
            refresh_token_plaintext="refresh-token",
            lwa_client=FakeLWAClient(),
            reports_client=FakeReportsClient(),
            downloaded_content=content,
        )
        assert sync_job.status == "imported"
        assert sync_job.import_job_id is not None
        assert sync_job.amazon_report_document_id == "document-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_sync_jobs.py -q
```

Expected: FAIL because `run_sync_job` and `refresh_sync_job` do not exist.

- [ ] **Step 3: Implement `run_sync_job`**

Modify `backend/app/services/amazon/sync_jobs.py`:

```python
from app.core.time import utc_now
from app.domain.enums import SPAPISyncJobErrorCode


def run_sync_job(
    *,
    session: Session,
    sync_job_id: int,
    refresh_token_plaintext: str,
    lwa_client,
    reports_client,
) -> SPAPISyncJob:
    sync_job = _get_sync_job(session, sync_job_id)
    try:
        token = lwa_client.exchange_refresh_token(refresh_token=refresh_token_plaintext)
        report_options = json.loads(sync_job.report_options_json or "{}")
        sync_job.amazon_report_id = reports_client.create_report(
            access_token=token.access_token,
            amazon_report_type=sync_job.amazon_report_type,
            marketplace_ids=[sync_job.marketplace.marketplace_id],
            date_range_start=sync_job.date_range_start,
            date_range_end=sync_job.date_range_end,
            report_options=report_options,
        )
        sync_job.status = SPAPISyncJobStatus.REQUESTED.value
        sync_job.requested_at = utc_now()
        sync_job.error_code = None
        sync_job.error_message = None
    except PermissionError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.PERMISSION_DENIED.value, str(exc))
    except Exception as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.UNEXPECTED_ERROR.value, str(exc))
    session.flush()
    return sync_job
```

Add helpers:

```python
def _get_sync_job(session: Session, sync_job_id: int) -> SPAPISyncJob:
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise SPAPISyncJobError("sync job not found")
    return sync_job


def _mark_failed(sync_job: SPAPISyncJob, error_code: str, error_message: str) -> None:
    sync_job.status = SPAPISyncJobStatus.FAILED.value
    sync_job.error_code = error_code
    sync_job.error_message = error_message
```

- [ ] **Step 4: Implement `refresh_sync_job`**

Add to `backend/app/services/amazon/sync_jobs.py`:

```python
from app.services.imports.spapi_ingestion import confirm_spapi_report_import


def refresh_sync_job(
    *,
    session: Session,
    storage,
    sync_job_id: int,
    refresh_token_plaintext: str,
    lwa_client,
    reports_client,
    downloaded_content: bytes | None = None,
) -> SPAPISyncJob:
    sync_job = _get_sync_job(session, sync_job_id)
    if not sync_job.amazon_report_id:
        raise SPAPISyncJobError("sync job has no Amazon report id")

    try:
        token = lwa_client.exchange_refresh_token(refresh_token=refresh_token_plaintext)
        status = reports_client.get_report(
            access_token=token.access_token,
            report_id=sync_job.amazon_report_id,
        )
        if status.processing_status in {"IN_QUEUE", "IN_PROGRESS"}:
            sync_job.status = SPAPISyncJobStatus.PROCESSING.value
            session.flush()
            return sync_job
        if status.processing_status != "DONE" or not status.report_document_id:
            _mark_failed(
                sync_job,
                SPAPISyncJobErrorCode.AMAZON_REPORT_FAILED.value,
                f"Amazon report status: {status.processing_status}",
            )
            session.flush()
            return sync_job

        document = reports_client.get_report_document(
            access_token=token.access_token,
            report_document_id=status.report_document_id,
        )
        sync_job.amazon_report_document_id = document.report_document_id
        content = downloaded_content
        if content is None:
            from app.services.amazon.report_downloads import download_report_document

            content = download_report_document(
                url=document.url,
                report_document_id=document.report_document_id,
                compression_algorithm=document.compression_algorithm,
            ).content
        response = confirm_spapi_report_import(
            session=session,
            storage=storage,
            seller_account_id=sync_job.seller_account_id,
            marketplace_id=sync_job.marketplace_id,
            internal_report_type=sync_job.internal_report_type,
            amazon_report_type=sync_job.amazon_report_type,
            date_range_start=sync_job.date_range_start,
            date_range_end=sync_job.date_range_end,
            original_filename=f"{document.report_document_id}.json",
            file_bytes=content,
        )
        sync_job.import_job_id = response.import_job_id
        sync_job.download_path = response.raw_file_path
        sync_job.status = SPAPISyncJobStatus.IMPORTED.value
        sync_job.completed_at = utc_now()
        sync_job.error_code = None
        sync_job.error_message = None
    except PermissionError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.PERMISSION_DENIED.value, str(exc))
    except ValueError as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.DUPLICATE_DATASET.value, str(exc))
    except Exception as exc:
        _mark_failed(sync_job, SPAPISyncJobErrorCode.UNEXPECTED_ERROR.value, str(exc))
    session.flush()
    return sync_job
```

- [ ] **Step 5: Wire API run/refresh endpoints**

Modify `backend/app/api/routes/spapi.py` to add:

```python
from app.api.deps import get_settings
from app.core.config import Settings
from app.core.storage import create_storage_backend
from app.services.amazon.lwa import LWAClient
from app.services.amazon.reports_client import AmazonReportsClient
from app.services.amazon.sync_jobs import refresh_sync_job, run_sync_job
from app.services.security.tokens import TokenCipher

SettingsDep = Annotated[Settings, Depends(get_settings)]
```

Add helper:

```python
def _decrypt_refresh_token(sync_job: SPAPISyncJob, settings: Settings) -> str:
    return TokenCipher(settings.TOKEN_ENCRYPTION_KEY or "").decrypt(
        sync_job.amazon_authorization.refresh_token_encrypted
    )
```

Add endpoints:

```python
@router.post("/sync-jobs/{sync_job_id}/run", response_model=SPAPISyncJobResponse)
def post_run_sync_job(sync_job_id: int, session: SessionDep, settings: SettingsDep):
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    refresh_token = _decrypt_refresh_token(sync_job, settings)
    result = run_sync_job(
        session=session,
        sync_job_id=sync_job_id,
        refresh_token_plaintext=refresh_token,
        lwa_client=LWAClient(
            token_url=settings.AMAZON_LWA_TOKEN_URL,
            client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            client_secret=settings.AMAZON_LWA_CLIENT_SECRET or "",
            timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
        ),
        reports_client=AmazonReportsClient(
            base_url=settings.AMAZON_SPAPI_BASE_URL,
            timeout_seconds=settings.AMAZON_REPORTS_TIMEOUT_SECONDS,
        ),
    )
    session.commit()
    return result


@router.post("/sync-jobs/{sync_job_id}/refresh", response_model=SPAPISyncJobResponse)
def post_refresh_sync_job(sync_job_id: int, session: SessionDep, settings: SettingsDep):
    sync_job = session.get(SPAPISyncJob, sync_job_id)
    if sync_job is None:
        raise HTTPException(status_code=404, detail="sync job not found")
    refresh_token = _decrypt_refresh_token(sync_job, settings)
    result = refresh_sync_job(
        session=session,
        storage=create_storage_backend(settings.STORAGE_ROOT),
        sync_job_id=sync_job_id,
        refresh_token_plaintext=refresh_token,
        lwa_client=LWAClient(
            token_url=settings.AMAZON_LWA_TOKEN_URL,
            client_id=settings.AMAZON_LWA_CLIENT_ID or "",
            client_secret=settings.AMAZON_LWA_CLIENT_SECRET or "",
            timeout_seconds=settings.AMAZON_LWA_TIMEOUT_SECONDS,
        ),
        reports_client=AmazonReportsClient(
            base_url=settings.AMAZON_SPAPI_BASE_URL,
            timeout_seconds=settings.AMAZON_REPORTS_TIMEOUT_SECONDS,
        ),
    )
    session.commit()
    return result
```

- [ ] **Step 6: Run tests**

Run:

```powershell
cd backend
python -m pytest tests/test_spapi_sync_jobs.py tests/test_api_spapi.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add backend/app/services/amazon/sync_jobs.py backend/app/api/routes/spapi.py backend/tests/test_spapi_sync_jobs.py backend/tests/test_api_spapi.py
git commit -m "feat: run spapi sync jobs"
```

---

### Task 7: Versioned LLM Prompts And Output Schema

**Files:**
- Create: `backend/app/services/llm/output_schema.py`
- Create: `backend/app/services/llm/prompt_registry.py`
- Create: `backend/app/services/llm/prompts/daily_report_v1/system.md`
- Create: `backend/app/services/llm/prompts/daily_report_v1/user.md`
- Modify: `backend/app/services/llm/openai_compatible.py`
- Modify: `backend/app/services/llm/provider.py`
- Modify: `backend/app/services/llm/validator.py`
- Modify: `backend/app/services/llm/snapshot.py`
- Test: `backend/tests/test_llm_v5.py`
- Test: `backend/tests/test_llm_openai_compatible.py`

- [ ] **Step 1: Write LLM schema tests**

Create `backend/tests/test_llm_v5.py`:

```python
from app.services.llm.output_schema import validate_daily_report_analysis
from app.services.llm.prompt_registry import load_prompt


def test_prompt_registry_loads_daily_report_v1() -> None:
    prompt = load_prompt("daily_report_v1")

    assert prompt.prompt_version == "daily_report_v1"
    assert "human review" in prompt.system_prompt.lower()
    assert "{{ snapshot_json }}" in prompt.user_prompt


def test_llm_schema_accepts_evidence_backed_output() -> None:
    output = {
        "summary": "Sales are stable.",
        "findings": [
            {
                "title": "Review SKU movement",
                "severity": "warning",
                "evidence_refs": ["store:1:marketplace:1:2026-05-20"],
                "reasoning": "Units changed from the imported report.",
                "recommended_human_actions": ["Review SKU level sales before changing anything."],
                "human_review_required": True,
            }
        ],
        "data_quality_notes": ["No freshness warnings."],
    }

    validated = validate_daily_report_analysis(
        output,
        evidence_ids={"store:1:marketplace:1:2026-05-20"},
    )

    assert validated.summary == "Sales are stable."
    assert validated.findings[0].severity == "warning"


def test_llm_schema_rejects_automatic_operations() -> None:
    output = {
        "summary": "Unsafe.",
        "findings": [
            {
                "title": "Unsafe action",
                "severity": "critical",
                "evidence_refs": ["store:1:marketplace:1:2026-05-20"],
                "reasoning": "The model tried to operate Amazon.",
                "recommended_human_actions": ["Automatically change price to 9.99."],
                "human_review_required": True,
            }
        ],
        "data_quality_notes": [],
    }

    try:
        validate_daily_report_analysis(
            output,
            evidence_ids={"store:1:marketplace:1:2026-05-20"},
        )
    except ValueError as exc:
        assert "automatic" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_llm_v5.py tests/test_llm_openai_compatible.py -q
```

Expected: FAIL because prompt registry and output schema do not exist.

- [ ] **Step 3: Add prompt files**

Create `backend/app/services/llm/prompts/daily_report_v1/system.md`:

```text
You analyze internal Amazon store performance data.
Return only JSON that matches the requested schema.
Every finding must cite evidence_refs from the provided snapshot.
Every recommended action must require human review.
Do not recommend automatic Amazon operations such as changing prices, editing listings, changing inventory, pausing campaigns, or modifying budgets.
Do not infer buyer personal information.
```

Create `backend/app/services/llm/prompts/daily_report_v1/user.md`:

```text
Analyze this normalized report snapshot and return JSON.

Snapshot:
{{ snapshot_json }}
```

- [ ] **Step 4: Add prompt registry**

Create `backend/app/services/llm/prompt_registry.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PromptTemplate:
    prompt_version: str
    output_schema_version: str
    system_prompt: str
    user_prompt: str


PROMPT_ROOT = Path(__file__).parent / "prompts"


class PromptNotFoundError(Exception):
    pass


def load_prompt(prompt_version: str) -> PromptTemplate:
    if prompt_version != "daily_report_v1":
        raise PromptNotFoundError(f"Prompt version not found: {prompt_version}")
    prompt_dir = PROMPT_ROOT / prompt_version
    return PromptTemplate(
        prompt_version=prompt_version,
        output_schema_version="daily_report_analysis.v1",
        system_prompt=(prompt_dir / "system.md").read_text(encoding="utf-8").strip(),
        user_prompt=(prompt_dir / "user.md").read_text(encoding="utf-8").strip(),
    )
```

- [ ] **Step 5: Add output schema**

Create `backend/app/services/llm/output_schema.py`:

```python
from pydantic import BaseModel, Field, field_validator


BLOCKED_ACTION_WORDS = (
    "automatically change",
    "auto change",
    "change bid",
    "change price",
    "edit listing",
    "pause campaign",
    "increase budget",
    "modify inventory",
)


class DailyReportFinding(BaseModel):
    title: str
    severity: str = Field(pattern="^(info|warning|critical)$")
    evidence_refs: list[str]
    reasoning: str
    recommended_human_actions: list[str]
    human_review_required: bool

    @field_validator("human_review_required")
    @classmethod
    def must_require_human_review(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Finding must require human review")
        return value


class DailyReportAnalysis(BaseModel):
    summary: str
    findings: list[DailyReportFinding]
    data_quality_notes: list[str] = Field(default_factory=list)


def validate_daily_report_analysis(
    output: dict[str, object],
    *,
    evidence_ids: set[str],
) -> DailyReportAnalysis:
    parsed = DailyReportAnalysis.model_validate(output)
    for finding in parsed.findings:
        if not finding.evidence_refs:
            raise ValueError("Finding missing evidence references")
        unknown_refs = set(finding.evidence_refs) - evidence_ids
        if unknown_refs:
            raise ValueError(f"Finding references evidence outside snapshot: {sorted(unknown_refs)}")
        actions_text = " ".join(finding.recommended_human_actions).lower()
        if any(blocked in actions_text for blocked in BLOCKED_ACTION_WORDS):
            raise ValueError("LLM output includes automatic Amazon operation recommendation")
    return parsed
```

- [ ] **Step 6: Bridge old validator to new schema**

Modify `backend/app/services/llm/validator.py`:

```python
from app.services.llm.output_schema import validate_daily_report_analysis


def validate_llm_output(
    output: dict[str, object],
    snapshot: dict[str, object],
) -> dict[str, object]:
    validated = validate_daily_report_analysis(
        output,
        evidence_ids=set(str(item) for item in snapshot.get("evidence_ids", [])),
    )
    return validated.model_dump(mode="json")
```

- [ ] **Step 7: Update mock provider output**

Modify `backend/app/services/llm/provider.py` so `MockLLMProvider.analyze()` returns:

```python
return {
    "summary": f"Daily report for {report_date} is ready for review.",
    "findings": [
        {
            "title": "Review daily changes",
            "severity": "warning",
            "evidence_refs": list(snapshot.get("evidence_ids", [f"report:{report_date}"]))[:1],
            "reasoning": "Imported report data changed from the normalized business data.",
            "recommended_human_actions": ["Review flagged stores before taking action."],
            "human_review_required": True,
        }
    ],
    "data_quality_notes": list(snapshot.get("warnings", [])),
}
```

- [ ] **Step 8: Update OpenAI-compatible provider to use prompts**

Modify `backend/app/services/llm/openai_compatible.py`:

```python
from app.services.llm.prompt_registry import load_prompt
```

Inside `analyze()` before the HTTP call:

```python
prompt = load_prompt("daily_report_v1")
snapshot_json = json.dumps(snapshot, ensure_ascii=False)
```

Replace hard-coded messages:

```python
"messages": [
    {"role": "system", "content": prompt.system_prompt},
    {
        "role": "user",
        "content": prompt.user_prompt.replace("{{ snapshot_json }}", snapshot_json),
    },
],
```

- [ ] **Step 9: Update snapshot evidence IDs**

Modify `backend/app/services/llm/snapshot.py`:

```python
def build_llm_snapshot(report: DailyReportDocument) -> dict[str, object]:
    evidence_ids = [
        (
            f"store:{summary.seller_account_id}:marketplace:"
            f"{summary.marketplace_id}:{report.report_date.isoformat()}"
        )
        for summary in report.store_summaries
    ]
    if not evidence_ids:
        evidence_ids = [f"report:{report.report_date.isoformat()}"]
    return {
        "report_date": report.report_date.isoformat(),
        "totals": {key: str(value) for key, value in report.totals.items()},
        "store_summaries": [summary.model_dump(mode="json") for summary in report.store_summaries],
        "warnings": report.warnings,
        "evidence_ids": evidence_ids,
    }
```

- [ ] **Step 10: Run LLM tests**

Run:

```powershell
cd backend
python -m pytest tests/test_llm.py tests/test_llm_v5.py tests/test_llm_openai_compatible.py -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

Run:

```powershell
git add backend/app/services/llm backend/tests/test_llm.py backend/tests/test_llm_v5.py backend/tests/test_llm_openai_compatible.py
git commit -m "feat: add versioned llm report schema"
```

---

### Task 8: Report Generation, Excel, And Markdown With AI Output

**Files:**
- Modify: `backend/app/schemas/reports.py`
- Modify: `backend/app/services/reports/generator.py`
- Modify: `backend/app/services/reports/excel.py`
- Modify: `backend/app/services/reports/markdown.py`
- Test: `backend/tests/test_report_generation_v2.py`
- Test: `backend/tests/test_report_excel_v5.py`

- [ ] **Step 1: Write Excel V5 test**

Create `backend/tests/test_report_excel_v5.py`:

```python
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd

from app.schemas.reports import DailyReportDocument, StoreDailySummary
from app.services.reports.excel import write_daily_report_excel


def test_v5_excel_contains_ai_and_sync_sheets(tmp_path: Path) -> None:
    report = DailyReportDocument(
        report_date=date(2026, 5, 20),
        store_summaries=[
            StoreDailySummary(
                seller_account_id=1,
                seller_name="US Store",
                marketplace_id="ATVPDKIKX0DER",
                ordered_product_sales=Decimal("125.50"),
                units_ordered=5,
                ad_spend=Decimal("0"),
                ad_sales=Decimal("0"),
                acos=Decimal("0"),
                data_status="stable",
            )
        ],
        totals={"ordered_product_sales": Decimal("125.50"), "units_ordered": Decimal("5")},
        warnings=["No freshness warnings."],
        llm_analysis={
            "summary": "Sales are stable.",
            "findings": [
                {
                    "title": "Review SKU movement",
                    "severity": "warning",
                    "evidence_refs": ["store:1:marketplace:ATVPDKIKX0DER:2026-05-20"],
                    "reasoning": "SKU sales changed.",
                    "recommended_human_actions": ["Review SKU before changing anything."],
                    "human_review_required": True,
                }
            ],
            "data_quality_notes": ["No freshness warnings."],
        },
        sync_sources=[
            {
                "source": "sp_api",
                "report_type": "business_report",
                "raw_file_checksum": "abc123",
            }
        ],
    )
    output_path = tmp_path / "report.xlsx"

    write_daily_report_excel(report, output_path)

    workbook = pd.ExcelFile(output_path)
    assert set(workbook.sheet_names) >= {
        "Overview",
        "Store Summary",
        "AI Insights",
        "Action Checklist",
        "Data Warnings",
        "Sync Jobs",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_report_excel_v5.py -q
```

Expected: FAIL because `DailyReportDocument` lacks `llm_analysis` and `sync_sources`, and Excel lacks V5 sheets.

- [ ] **Step 3: Extend report document schema**

Modify `backend/app/schemas/reports.py`:

```python
from typing import Any
from pydantic import Field
```

Add fields:

```python
class DailyReportDocument(BaseModel):
    report_date: date
    store_summaries: list[StoreDailySummary]
    totals: dict[str, Decimal]
    warnings: list[str]
    llm_analysis: dict[str, Any] | None = None
    sync_sources: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Update report generator to run LLM**

Modify `backend/app/services/reports/generator.py`:

```python
from app.core.config import Settings
from app.services.llm.openai_compatible import OpenAICompatibleLLMProvider
from app.services.llm.provider import MockLLMProvider
from app.services.llm.snapshot import build_llm_snapshot
```

Inside `generate_report()` after `document = build_daily_report(...)`:

```python
settings = Settings()
snapshot = build_llm_snapshot(document)
if settings.LLM_PROVIDER == "mock":
    llm_output = MockLLMProvider().analyze(snapshot)
    llm_status = LLMStatus.SUCCEEDED.value
    llm_error = None
    model_name = "mock"
else:
    llm_result = OpenAICompatibleLLMProvider(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    ).analyze(snapshot)
    llm_output = llm_result.output
    llm_status = llm_result.status
    llm_error = llm_result.error
    model_name = settings.LLM_MODEL
document.llm_analysis = llm_output
document.sync_sources = _build_sync_sources(rows)
```

Add helper:

```python
def _build_sync_sources(rows: list[NormalizedBusinessDaily]) -> list[dict[str, object]]:
    seen: dict[int, dict[str, object]] = {}
    for row in rows:
        dataset = row.raw_dataset
        seen[dataset.id] = {
            "raw_dataset_id": dataset.id,
            "source": dataset.source,
            "report_type": dataset.report_type,
            "raw_file_path": dataset.raw_file_path,
            "raw_file_checksum": dataset.raw_file_checksum,
            "data_status": dataset.data_status,
        }
    return list(seen.values())
```

Set `DailyReport` fields:

```python
prompt_version="daily_report_v1",
model_name=model_name,
llm_status=llm_status,
llm_error=llm_error,
```

- [ ] **Step 5: Update Excel writer**

Modify `backend/app/services/reports/excel.py`:

```python
overview = [{"metric": key, "value": str(value)} for key, value in report.totals.items()]
ai = report.llm_analysis or {}
findings = ai.get("findings", []) if isinstance(ai, dict) else []
actions = [
    {
        "title": finding.get("title"),
        "action": action,
        "human_review_required": finding.get("human_review_required"),
    }
    for finding in findings
    for action in finding.get("recommended_human_actions", [])
]
```

Write sheets:

```python
pd.DataFrame(overview).to_excel(writer, sheet_name="Overview", index=False)
pd.DataFrame(rows).to_excel(writer, sheet_name="Store Summary", index=False)
pd.DataFrame(findings).to_excel(writer, sheet_name="AI Insights", index=False)
pd.DataFrame(actions).to_excel(writer, sheet_name="Action Checklist", index=False)
pd.DataFrame(warnings).to_excel(writer, sheet_name="Data Warnings", index=False)
pd.DataFrame(report.sync_sources).to_excel(writer, sheet_name="Sync Jobs", index=False)
```

- [ ] **Step 6: Update markdown**

Modify `backend/app/services/reports/markdown.py` to add after Store Summary:

```python
analysis = report.llm_analysis or {}
if isinstance(analysis, dict) and analysis.get("summary"):
    lines.extend(["", "## AI Insights", f"- {analysis['summary']}"])
    for finding in analysis.get("findings", []):
        lines.append(f"- {finding.get('severity', 'info')}: {finding.get('title', '')}")
```

- [ ] **Step 7: Run report tests**

Run:

```powershell
cd backend
python -m pytest tests/test_report_generation_v2.py tests/test_report_excel_v5.py tests/test_reports.py tests/test_api_reports_v2.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/app/schemas/reports.py backend/app/services/reports/generator.py backend/app/services/reports/excel.py backend/app/services/reports/markdown.py backend/tests/test_report_generation_v2.py backend/tests/test_report_excel_v5.py
git commit -m "feat: add ai insights to reports"
```

---

### Task 9: Web UI Store Selection And SP-API Sync Page

**Files:**
- Modify: `backend/app/web/routes.py`
- Modify: `backend/app/web/templates/base.html`
- Create: `backend/app/web/templates/spapi_sync.html`
- Modify: `backend/app/web/templates/imports.html`
- Modify: `backend/app/web/templates/reports.html`
- Modify: `backend/app/web/templates/settings.html`
- Test: `backend/tests/test_web_v5.py`

- [ ] **Step 1: Write web tests**

Create `backend/tests/test_web_v5.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_spapi_sync_page_is_available_and_uses_store_options() -> None:
    client = TestClient(create_app())

    response = client.get("/spapi-sync")

    assert response.status_code == 200
    assert "SP-API 同步" in response.text
    assert "/api/settings/store-options" in response.text
    assert "/api/spapi/report-types" in response.text
    assert "/api/spapi/sync-jobs" in response.text


def test_import_and_report_pages_no_longer_show_numeric_store_inputs() -> None:
    client = TestClient(create_app())

    imports = client.get("/imports").text
    reports = client.get("/reports").text

    assert 'name="seller_account_id" inputmode="numeric"' not in imports
    assert 'name="marketplace_id" inputmode="numeric"' not in imports
    assert 'name="seller_account_id" inputmode="numeric"' not in reports
    assert 'name="marketplace_id" inputmode="numeric"' not in reports
    assert "store-options" in imports
    assert "store-options" in reports
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v5.py -q
```

Expected: FAIL because `/spapi-sync` page and dropdown flows do not exist.

- [ ] **Step 3: Add web route and navigation**

Modify `backend/app/web/routes.py`:

```python
@router.get("/spapi-sync")
def spapi_sync_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="spapi_sync.html",
        context={"title": "SP-API Sync"},
    )
```

Modify `backend/app/web/templates/base.html` navigation:

```html
<a href="/spapi-sync">SP-API Sync</a>
```

- [ ] **Step 4: Create sync page**

Create `backend/app/web/templates/spapi_sync.html` with JSON fetch behavior:

```html
{% extends "base.html" %}
{% block content %}
<h1>SP-API 同步</h1>
<section>
  <h2>创建同步任务</h2>
  <form id="spapi-sync-form">
    <label>店铺/市场 <select name="store_option" id="store-option"></select></label>
    <label>报表类型 <select name="internal_report_type" id="report-type"></select></label>
    <label>开始日期 <input name="date_range_start" type="date" required></label>
    <label>结束日期 <input name="date_range_end" type="date" required></label>
    <div class="actions">
      <button type="submit">创建并运行同步</button>
      <button type="button" id="refresh-jobs" class="secondary">刷新任务</button>
    </div>
    <p id="sync-message" role="status"></p>
  </form>
</section>
<section>
  <h2>同步任务</h2>
  <table>
    <thead>
      <tr><th>ID</th><th>报表</th><th>日期</th><th>状态</th><th>Amazon Report ID</th><th>操作</th></tr>
    </thead>
    <tbody id="sync-jobs"><tr><td colspan="6">No sync jobs yet.</td></tr></tbody>
  </table>
</section>
<script>
async function jsonFetch(url, options = {}) {
  const response = await fetch(url, {
    headers: {"Content-Type": "application/json"},
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || response.statusText);
  }
  return response.json();
}
async function loadOptions() {
  const stores = await jsonFetch("/api/settings/store-options");
  document.getElementById("store-option").innerHTML = stores.map((item) =>
    `<option value="${item.seller_account_id}:${item.marketplace_id}">${item.label}</option>`
  ).join("");
  const reportTypes = await jsonFetch("/api/spapi/report-types");
  document.getElementById("report-type").innerHTML = reportTypes.map((item) =>
    `<option value="${item.internal_report_type}">${item.display_name}</option>`
  ).join("");
}
async function loadJobs() {
  const jobs = await jsonFetch("/api/spapi/sync-jobs");
  document.getElementById("sync-jobs").innerHTML = jobs.length ? jobs.map((job) =>
    `<tr>
      <td>${job.id}</td>
      <td>${job.internal_report_type}</td>
      <td>${job.date_range_start} - ${job.date_range_end}</td>
      <td>${job.status}</td>
      <td>${job.amazon_report_id || ""}</td>
      <td><button type="button" data-refresh="${job.id}">刷新状态</button></td>
    </tr>`
  ).join("") : `<tr><td colspan="6">No sync jobs yet.</td></tr>`;
}
document.getElementById("spapi-sync-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const [seller_account_id, marketplace_id] = form.get("store_option").split(":").map(Number);
  const job = await jsonFetch("/api/spapi/sync-jobs", {
    method: "POST",
    body: JSON.stringify({
      seller_account_id,
      marketplace_id,
      internal_report_type: form.get("internal_report_type"),
      date_range_start: form.get("date_range_start"),
      date_range_end: form.get("date_range_end"),
      report_options: {},
    }),
  });
  await jsonFetch(`/api/spapi/sync-jobs/${job.id}/run`, {method: "POST"});
  document.getElementById("sync-message").textContent = "同步任务已创建。稍后点击刷新状态。";
  await loadJobs();
});
document.getElementById("sync-jobs").addEventListener("click", async (event) => {
  const id = event.target.dataset.refresh;
  if (id) {
    await jsonFetch(`/api/spapi/sync-jobs/${id}/refresh`, {method: "POST"});
    await loadJobs();
  }
});
document.getElementById("refresh-jobs").addEventListener("click", loadJobs);
loadOptions().then(loadJobs);
</script>
{% endblock %}
```

- [ ] **Step 5: Update imports and reports pages**

Modify `backend/app/web/templates/imports.html` and `backend/app/web/templates/reports.html`:

- Replace numeric seller/marketplace inputs with:

```html
<label>店铺/市场 <select name="store_option" id="store-option"></select></label>
<input type="hidden" name="seller_account_id" id="seller-account-id">
<input type="hidden" name="marketplace_id" id="marketplace-id">
```

Use this shared store-option script shape in both pages:

```html
<script>
async function loadStoreOptions() {
  const response = await fetch("/api/settings/store-options");
  const stores = await response.json();
  const select = document.getElementById("store-option");
  select.innerHTML = stores.map((item) =>
    `<option value="${item.seller_account_id}:${item.marketplace_id}">${item.label}</option>`
  ).join("");
  syncStoreHiddenFields();
}
function syncStoreHiddenFields() {
  const [sellerAccountId, marketplaceId] = document
    .getElementById("store-option")
    .value
    .split(":");
  document.getElementById("seller-account-id").value = sellerAccountId;
  document.getElementById("marketplace-id").value = marketplaceId;
}
document.getElementById("store-option").addEventListener("change", syncStoreHiddenFields);
loadStoreOptions();
</script>
```

For `backend/app/web/templates/reports.html`, remove `method="post" action="/api/reports/generate"` and add JSON submit:

```html
<p id="report-message" role="status"></p>
<script>
document.querySelector("form").addEventListener("submit", async (event) => {
  event.preventDefault();
  syncStoreHiddenFields();
  const form = new FormData(event.target);
  const scopeType = form.get("scope_type");
  const payload = {
    scope_type: scopeType,
    report_kind: form.get("report_kind"),
    report_start_date: form.get("report_start_date"),
    report_end_date: form.get("report_end_date"),
    seller_account_id: scopeType === "single_store" ? Number(form.get("seller_account_id")) : null,
    marketplace_id: scopeType === "single_store" ? Number(form.get("marketplace_id")) : null,
  };
  const response = await fetch("/api/reports/generate", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  document.getElementById("report-message").textContent = response.ok
    ? `报告已生成：#${result.id}`
    : (result.detail || "报告生成失败");
});
</script>
```

For `backend/app/web/templates/imports.html`, keep multipart upload and hidden ids. The existing `/api/imports/preview` and `/api/imports/confirm` endpoints already accept multipart form data, so the submit buttons remain browser form posts after hidden ids are synchronized.

- [ ] **Step 6: Update settings page lists**

Modify `backend/app/web/templates/settings.html`:

- Load and display `/api/settings/seller-accounts`.
- Load and display `/api/auth/amazon/authorizations`.
- Make SP-API self authorization select a seller account from loaded sellers.
- On seller selection, auto-fill `selling_partner_id` with `amazon_seller_id`.
- Keep refresh token input masked and clear after successful save.

Add these elements near the existing seller and authorization forms:

```html
<section>
  <h2>已保存店铺</h2>
  <table>
    <thead><tr><th>ID</th><th>显示名称</th><th>卖家记号</th><th>状态</th></tr></thead>
    <tbody id="seller-accounts"><tr><td colspan="4">No seller accounts yet.</td></tr></tbody>
  </table>
</section>
<section>
  <h2>已保存 SP-API 授权</h2>
  <table>
    <thead><tr><th>ID</th><th>卖方伙伴身份</th><th>绑定店铺</th><th>状态</th></tr></thead>
    <tbody id="amazon-authorizations"><tr><td colspan="4">No authorizations yet.</td></tr></tbody>
  </table>
</section>
```

Add this script after the existing `submitJsonForm` helper:

```html
<script>
let savedSellers = [];
async function loadSellerAccounts() {
  const response = await fetch("/api/settings/seller-accounts");
  savedSellers = await response.json();
  document.getElementById("seller-accounts").innerHTML = savedSellers.length
    ? savedSellers.map((item) =>
      `<tr><td>${item.id}</td><td>${item.display_name}</td><td>${item.amazon_seller_id}</td><td>${item.is_active}</td></tr>`
    ).join("")
    : `<tr><td colspan="4">No seller accounts yet.</td></tr>`;
  const select = document.getElementById("authorization-seller-account");
  if (select) {
    select.innerHTML = savedSellers.map((item) =>
      `<option value="${item.id}" data-seller-id="${item.amazon_seller_id}">${item.display_name} - ${item.amazon_seller_id}</option>`
    ).join("");
    fillAuthorizationSellingPartnerId();
  }
}
async function loadAmazonAuthorizations() {
  const response = await fetch("/api/auth/amazon/authorizations");
  const authorizations = await response.json();
  document.getElementById("amazon-authorizations").innerHTML = authorizations.length
    ? authorizations.map((item) =>
      `<tr><td>${item.id}</td><td>${item.selling_partner_id}</td><td>${item.seller_account_id || ""}</td><td>${item.status}</td></tr>`
    ).join("")
    : `<tr><td colspan="4">No authorizations yet.</td></tr>`;
}
function fillAuthorizationSellingPartnerId() {
  const select = document.getElementById("authorization-seller-account");
  const selected = select?.selectedOptions[0];
  const input = document.querySelector('[name="selling_partner_id"]');
  if (selected && input) input.value = selected.dataset.sellerId || "";
}
document.getElementById("authorization-seller-account")?.addEventListener("change", fillAuthorizationSellingPartnerId);
loadSellerAccounts().then(loadAmazonAuthorizations);
</script>
```

- [ ] **Step 7: Run web tests**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v2.py tests/test_web_v5.py -q
```

Expected: PASS. If V2 text assertions conflict with clearer V5 Chinese labels, update `tests/test_web_v2.py` to assert the new labels that actually appear in templates.

- [ ] **Step 8: Commit**

Run:

```powershell
git add backend/app/web/routes.py backend/app/web/templates/base.html backend/app/web/templates/spapi_sync.html backend/app/web/templates/imports.html backend/app/web/templates/reports.html backend/app/web/templates/settings.html backend/tests/test_web_v5.py backend/tests/test_web_v2.py
git commit -m "feat: add v5 spapi sync ui"
```

---

### Task 10: Documentation And Final Verification

**Files:**
- Modify: `docs/api-readiness/amazon-api-readiness.md`
- Modify: `README.md`
- Test: full backend tests and lint

- [ ] **Step 1: Update API readiness**

Modify `docs/api-readiness/amazon-api-readiness.md`:

- Remove “Configure AWS IAM role and policy for SP-API” as a required item.
- Add “SP-API no longer requires AWS IAM or AWS Signature Version 4 as of 2023-10-02; use LWA access token.”
- Add V5 allowed roles and blocked roles.
- Add V5 initial enabled report: `business_sales_traffic -> GET_SALES_AND_TRAFFIC_REPORT`.
- State that Reports API data is raw report data and must pass through RawDataset and normalization.

- [ ] **Step 2: Update README**

Modify `README.md`:

- Add V5 current features: SP-API Sync page, report type registry, manual sync jobs, sales and traffic ingestion, AI insights Excel.
- Remove stale note saying SP-API signing is unfinished as a blocker.
- Keep warning that the app does not need public callback URL for self-authorization.
- Add local test command:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/spapi/report-types
```

- Add manual UI flow:

```text
Settings -> create seller account -> save SP-API self authorization -> create marketplace -> SP-API Sync -> create/run sync job -> refresh -> Reports -> generate report -> download Excel
```

- [ ] **Step 3: Run full verification**

Run:

```powershell
cd backend
python -m pytest -q
python -m ruff check .
python -m alembic upgrade head
```

Expected: all tests pass, ruff passes, migration reaches head.

- [ ] **Step 4: Manual browser smoke test**

Start app:

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

Open:

```text
http://127.0.0.1:8000/settings
http://127.0.0.1:8000/spapi-sync
http://127.0.0.1:8000/reports
```

Verify:

- Settings shows seller list and authorization list.
- SP-API Sync page loads store options and only one enabled report type.
- Imports and Reports no longer require numeric internal ids.
- Report Excel download works after data exists.

- [ ] **Step 5: Commit**

Run:

```powershell
git add docs/api-readiness/amazon-api-readiness.md README.md
git commit -m "docs: document v5 spapi sync flow"
```

---

## Final Acceptance Checklist

- [ ] `GET /api/spapi/report-types` returns only `business_sales_traffic`.
- [ ] Disabled report types cannot create sync jobs.
- [ ] Sync jobs require an active authorization bound to the seller.
- [ ] `POST /api/spapi/sync-jobs/{id}/run` creates an Amazon report request.
- [ ] `POST /api/spapi/sync-jobs/{id}/refresh` can import a completed sales-and-traffic report.
- [ ] Imported SP-API report creates `ImportJob(source="sp_api")`.
- [ ] Imported SP-API report creates RawDataset and RawReportRows.
- [ ] Imported SP-API sales-and-traffic rows create `NormalizedBusinessDaily`.
- [ ] LLM prompts load from versioned prompt files.
- [ ] LLM output validates against schema and evidence ids.
- [ ] Excel includes Overview, Store Summary, AI Insights, Action Checklist, Data Warnings, and Sync Jobs.
- [ ] `/spapi-sync` page exists and uses store dropdowns.
- [ ] `/imports` and `/reports` stop requiring numeric internal ids.
- [ ] README explains the V5 manual flow.
- [ ] `python -m pytest -q` passes.
- [ ] `python -m ruff check .` passes.
- [ ] `python -m alembic upgrade head` passes.
