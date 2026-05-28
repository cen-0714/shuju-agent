# Amazon Daily Copilot V2 Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the V2 internal operations workflow: maintain stores, confirm manual imports into the database, generate single-day and date-range reports, download Excel reports, and optionally call an OpenAI-compatible LLM.

**Architecture:** Extend the existing FastAPI monolith. Keep the V1 raw -> normalized -> metrics -> report pipeline, but make it persistent and user-driven through Settings, Data Import, Report Center, and Dashboard pages. V2 uses synchronous report generation and a local `StorageBackend`; API integrations, auth, async jobs, and push notifications remain out of scope.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL, SQLite for tests, Jinja2, pandas, XlsxWriter, httpx, pytest, ruff, Docker Compose.

---

## Scope Check

This plan implements `docs/superpowers/specs/2026-05-28-amazon-daily-copilot-v2-operations-design.md`.

V2 includes:

- Store configuration for `SellerAccount + Marketplace`.
- Import preview plus confirm.
- Local raw file storage.
- Raw row persistence.
- Normalized row persistence for Business, Inventory, and Ads Search Term reports.
- Import deletion and stale report marking.
- Report generation for single-day and date-range scopes.
- Report list, detail, Markdown, Excel download, and regenerate endpoints.
- OpenAI-compatible LLM provider, optional and non-blocking.
- Server-rendered UI upgrades for the existing four pages.

V2 excludes:

- Amazon SP-API and Ads API live integration.
- Login and permission management.
- Async queue or background workers.
- Automatic report push.
- Complex trend BI and forecasts.

## File Structure

Modify or create these files:

```text
backend/app/domain/enums.py
backend/app/core/config.py
backend/app/core/storage.py
backend/app/models/imports.py
backend/app/models/normalized.py
backend/app/models/reports.py
backend/app/models/audit.py
backend/app/models/settings.py
backend/app/schemas/imports.py
backend/app/schemas/reports.py
backend/app/schemas/settings.py
backend/app/services/settings.py
backend/app/services/imports/orchestrator.py
backend/app/services/imports/persistence.py
backend/app/services/imports/deletion.py
backend/app/services/normalization/persistence.py
backend/app/services/metrics/persistence.py
backend/app/services/reports/generator.py
backend/app/services/reports/repository.py
backend/app/services/llm/provider.py
backend/app/services/llm/openai_compatible.py
backend/app/api/routes/imports.py
backend/app/api/routes/reports.py
backend/app/api/routes/settings.py
backend/app/main.py
backend/app/web/routes.py
backend/app/web/templates/dashboard.html
backend/app/web/templates/imports.html
backend/app/web/templates/reports.html
backend/app/web/templates/settings.html
backend/app/web/static/app.css
backend/migrations/versions/20260528_0001_v2_operations.py
backend/tests/test_v2_models.py
backend/tests/test_api_settings_v2.py
backend/tests/test_storage.py
backend/tests/test_import_confirm.py
backend/tests/test_import_delete.py
backend/tests/test_report_generation_v2.py
backend/tests/test_api_reports_v2.py
backend/tests/test_llm_openai_compatible.py
backend/tests/test_web_v2.py
```

Responsibilities:

- `services/settings.py`: CRUD helpers for organizations, seller accounts, marketplaces, and store options.
- `services/imports/persistence.py`: confirm previewed files into raw datasets and raw rows.
- `services/imports/deletion.py`: delete import artifacts and mark reports stale.
- `services/normalization/persistence.py`: write normalized rows for supported report types.
- `services/metrics/persistence.py`: recalculate persisted daily metrics from normalized rows.
- `services/reports/generator.py`: generate scoped reports from persisted data.
- `services/reports/repository.py`: list, fetch, stale, and regenerate report records.
- `services/llm/openai_compatible.py`: call OpenAI-compatible chat completions with timeout and validation.

## Task 1: V2 Enums, Models, and Migration

**Files:**
- Modify: `backend/app/domain/enums.py`
- Modify: `backend/app/models/imports.py`
- Modify: `backend/app/models/normalized.py`
- Modify: `backend/app/models/reports.py`
- Modify: `backend/app/models/audit.py`
- Modify: `backend/app/models/settings.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_v2_models.py`
- Create: `backend/migrations/versions/20260528_0001_v2_operations.py`

- [ ] **Step 1: Write model tests**

Create `backend/tests/test_v2_models.py`:

```python
from datetime import date

from app.core.db import create_session_factory, create_sync_engine
from app.domain.enums import ImportJobStatus, ReportKind, ReportScopeType, ReportStatus
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset, RawReportRow
from app.models.normalized import NormalizedBusinessDaily
from app.models.reports import DailyReport
from app.models.settings import Marketplace, Organization, SellerAccount


def test_v2_enums_have_required_values() -> None:
    assert ImportJobStatus.PREVIEWED.value == "previewed"
    assert ImportJobStatus.DELETED.value == "deleted"
    assert ReportScopeType.ALL_STORES.value == "all_stores"
    assert ReportScopeType.SINGLE_STORE.value == "single_store"
    assert ReportKind.SINGLE_DAY.value == "single_day"
    assert ReportKind.DATE_RANGE.value == "date_range"
    assert ReportStatus.ACTIVE.value == "active"
    assert ReportStatus.STALE.value == "stale"


def test_v2_models_can_persist_import_and_report_scope() -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="Store A",
            amazon_seller_id="SELLER-A",
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
            date_range_start=date(2026, 5, 27),
            date_range_end=date(2026, 5, 27),
            status="succeeded",
            original_filename="business.csv",
        )
        dataset = RawDataset(
            import_job=job,
            seller_account=seller,
            marketplace=marketplace,
            source="manual_file",
            report_type="business_report",
            date_range_start=date(2026, 5, 27),
            date_range_end=date(2026, 5, 27),
            schema_version="business_report.v1",
            raw_file_path="backend/storage/raw/business.csv",
            raw_file_checksum="abc123",
            row_count=1,
            data_status="stable",
            data_version="business_report:2026-05-27:abc123",
        )
        raw_row = RawReportRow(raw_dataset=dataset, row_number=1, row_json='{"Date":"2026-05-27"}')
        normalized = NormalizedBusinessDaily(
            raw_dataset=dataset,
            seller_account=seller,
            marketplace=marketplace,
            report_date=date(2026, 5, 27),
            asin=None,
            sku=None,
            ordered_product_sales=100,
            units_ordered=4,
            sessions=40,
            page_views=80,
            conversion_rate=None,
            buy_box_percentage=None,
        )
        report = DailyReport(
            organization=org,
            scope_type="single_store",
            seller_account=seller,
            marketplace=marketplace,
            report_kind="single_day",
            report_start_date=date(2026, 5, 27),
            report_end_date=date(2026, 5, 27),
            report_version=1,
            status="active",
            data_version="business_report:2026-05-27:abc123",
            metric_definition_version="v1",
            prompt_version="v1",
            model_name="mock",
            report_json="{}",
            markdown="ok",
            markdown_path="backend/storage/reports/markdown/report.md",
            excel_path="backend/storage/reports/excel/report.xlsx",
            llm_status="skipped",
        )
        session.add_all([raw_row, normalized, report])
        session.commit()

        assert dataset.raw_rows[0].row_number == 1
        assert report.scope_type == "single_store"
        assert report.report_start_date == date(2026, 5, 27)
```

- [ ] **Step 2: Run model tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_v2_models.py -v
```

Expected: FAIL because V2 enums and model columns/relationships do not exist.

- [ ] **Step 3: Extend enums**

Modify `backend/app/domain/enums.py`:

```python
class ImportJobStatus(StrEnum):
    PENDING = "pending"
    PREVIEWED = "previewed"
    VALIDATED = "validated"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DELETED = "deleted"


class ReportScopeType(StrEnum):
    ALL_STORES = "all_stores"
    SINGLE_STORE = "single_store"


class ReportKind(StrEnum):
    SINGLE_DAY = "single_day"
    DATE_RANGE = "date_range"


class ReportStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    FAILED = "failed"


class LLMStatus(StrEnum):
    SKIPPED = "skipped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
```

Keep existing enum values unchanged.

- [ ] **Step 4: Extend ORM relationships and columns**

Implement these model changes:

- `ImportJob.original_filename: str | None`
- `ImportJob.deleted_at: datetime | None`
- `RawDataset.raw_rows` relationship
- `RawReportRow.raw_dataset` relationship
- `NormalizedBusinessDaily.raw_dataset`, `seller_account`, `marketplace` relationships
- `DailyReport.organization`, `seller_account`, `marketplace` relationships
- `DailyReport.scope_type`
- `DailyReport.seller_account_id` nullable
- `DailyReport.marketplace_id` nullable
- `DailyReport.report_kind`
- `DailyReport.report_start_date`
- `DailyReport.report_end_date`
- `DailyReport.status`
- `DailyReport.markdown_path`
- `DailyReport.llm_status`
- `DailyReport.llm_error`

Preserve V1 fields where possible. Keep `report_date` temporarily for backward compatibility, but make it mirror `report_start_date` for single-day reports in service code.

- [ ] **Step 5: Create Alembic migration**

Create `backend/migrations/versions/20260528_0001_v2_operations.py` manually using
`down_revision = "3d4526765c0a"` and `revision = "20260528_0001"`.

The migration must:

- Add new columns to `import_jobs`.
- Add new columns to `daily_reports`.
- Add nullable foreign keys from `daily_reports` to `seller_accounts` and `marketplaces`.
- Preserve existing tables.

- [ ] **Step 6: Run model tests**

Run:

```powershell
cd backend
python -m pytest tests/test_v2_models.py -v
```

Expected: `2 passed`.

- [ ] **Step 7: Run migration against SQLite smoke database**

Run:

```powershell
cd backend
$env:DATABASE_URL='sqlite+pysqlite:///./v2-model-check.sqlite'
python -m alembic upgrade head
Remove-Item .\v2-model-check.sqlite
```

Expected: migration completes without errors.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/domain/enums.py backend/app/models backend/migrations/versions backend/tests/test_v2_models.py
git commit -m "feat: extend models for v2 operations"
```

## Task 2: Store Settings API

**Files:**
- Modify: `backend/app/schemas/settings.py`
- Create: `backend/app/services/settings.py`
- Modify: `backend/app/api/routes/settings.py`
- Create: `backend/tests/test_api_settings_v2.py`

- [ ] **Step 1: Write settings API tests**

Create `backend/tests/test_api_settings_v2.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_store_settings_crud_flow() -> None:
    client = TestClient(create_app())

    seller_response = client.post(
        "/api/settings/seller-accounts",
        json={"display_name": "Store A", "amazon_seller_id": "SELLER-A"},
    )
    assert seller_response.status_code == 200
    seller = seller_response.json()
    assert seller["display_name"] == "Store A"

    marketplace_response = client.post(
        "/api/settings/marketplaces",
        json={
            "seller_account_id": seller["id"],
            "marketplace_id": "ATVPDKIKX0DER",
            "region": "americas",
            "country_code": "US",
            "timezone": "America/Los_Angeles",
            "currency_code": "USD",
        },
    )
    assert marketplace_response.status_code == 200
    marketplace = marketplace_response.json()
    assert marketplace["country_code"] == "US"

    options_response = client.get("/api/settings/store-options")
    assert options_response.status_code == 200
    options = options_response.json()
    assert options[0]["seller_account_id"] == seller["id"]
    assert options[0]["marketplace_id"] == marketplace["id"]
    assert options[0]["label"] == "Store A - US"


def test_can_disable_marketplace() -> None:
    client = TestClient(create_app())
    seller = client.post(
        "/api/settings/seller-accounts",
        json={"display_name": "Store B", "amazon_seller_id": "SELLER-B"},
    ).json()
    marketplace = client.post(
        "/api/settings/marketplaces",
        json={
            "seller_account_id": seller["id"],
            "marketplace_id": "A2EUQ1WTGCTBG2",
            "region": "americas",
            "country_code": "CA",
            "timezone": "America/Toronto",
            "currency_code": "CAD",
        },
    ).json()

    response = client.patch(f"/api/settings/marketplaces/{marketplace['id']}", json={"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_api_settings_v2.py -v
```

Expected: FAIL because endpoints do not exist.

- [ ] **Step 3: Add settings schemas**

Add these Pydantic models to `backend/app/schemas/settings.py`:

```python
class SellerAccountCreate(BaseModel):
    display_name: str
    amazon_seller_id: str


class SellerAccountUpdate(BaseModel):
    display_name: str | None = None
    amazon_seller_id: str | None = None
    is_active: bool | None = None


class SellerAccountResponse(BaseModel):
    id: int
    display_name: str
    amazon_seller_id: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class MarketplaceCreate(BaseModel):
    seller_account_id: int
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str


class MarketplaceUpdate(BaseModel):
    region: str | None = None
    country_code: str | None = None
    timezone: str | None = None
    currency_code: str | None = None
    is_active: bool | None = None


class MarketplaceResponse(BaseModel):
    id: int
    seller_account_id: int
    marketplace_id: str
    region: str
    country_code: str
    timezone: str
    currency_code: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class StoreOption(BaseModel):
    seller_account_id: int
    marketplace_id: int
    label: str
    region: str
    country_code: str
    currency_code: str
```

Also import `ConfigDict`.

- [ ] **Step 4: Implement settings service**

Create `backend/app/services/settings.py` with functions:

- `ensure_default_organization(session) -> Organization`
- `create_seller_account(session, payload) -> SellerAccount`
- `update_seller_account(session, seller_account_id, payload) -> SellerAccount`
- `list_seller_accounts(session) -> list[SellerAccount]`
- `create_marketplace(session, payload) -> Marketplace`
- `update_marketplace(session, marketplace_id, payload) -> Marketplace`
- `list_marketplaces(session) -> list[Marketplace]`
- `list_store_options(session) -> list[StoreOption]`

Use the existing `Organization` model and default organization:

```python
DEFAULT_ORG_NAME = "Internal Team"
DEFAULT_ORG_SLUG = "internal"
```

Return 404 through `ValueError` from service and translate to HTTP 404 in route code.

- [ ] **Step 5: Implement settings routes**

Modify `backend/app/api/routes/settings.py` to add:

```text
GET    /seller-accounts
POST   /seller-accounts
PATCH  /seller-accounts/{seller_account_id}
GET    /marketplaces
POST   /marketplaces
PATCH  /marketplaces/{marketplace_id}
GET    /store-options
```

Use `Depends(get_session)` and commit writes inside route functions.

- [ ] **Step 6: Run settings API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_settings_v2.py -v
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/schemas/settings.py backend/app/services/settings.py backend/app/api/routes/settings.py backend/tests/test_api_settings_v2.py
git commit -m "feat: add store settings api"
```

## Task 3: Local Storage Backend

**Files:**
- Modify: `backend/app/core/storage.py`
- Modify: `backend/app/core/config.py`
- Create: `backend/tests/test_storage.py`

- [ ] **Step 1: Write storage tests**

Create `backend/tests/test_storage.py`:

```python
from pathlib import Path

from app.core.storage import LocalStorageBackend


def test_local_storage_saves_and_deletes_file(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root=tmp_path)

    saved = storage.save_upload(
        category="raw",
        filename="business.csv",
        content=b"Date,Sales\n2026-05-27,100\n",
    )

    assert saved.relative_path.startswith("raw/")
    assert saved.absolute_path.exists()
    assert saved.checksum
    assert saved.size_bytes > 0

    storage.delete_file(saved.relative_path)

    assert not saved.absolute_path.exists()


def test_local_storage_resolve_rejects_escape(tmp_path: Path) -> None:
    storage = LocalStorageBackend(root=tmp_path)

    try:
        storage.resolve_path("../outside.csv")
    except ValueError as exc:
        assert "outside storage root" in str(exc)
    else:
        raise AssertionError("Expected path escape to fail")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_storage.py -v
```

Expected: FAIL because `LocalStorageBackend` does not support these methods.

- [ ] **Step 3: Implement storage backend**

Modify `backend/app/core/storage.py`:

```python
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class StoredFile:
    relative_path: str
    absolute_path: Path
    checksum: str
    size_bytes: int


class LocalStorageBackend:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(self, *, category: str, filename: str, content: bytes) -> StoredFile:
        safe_name = Path(filename).name or "upload.dat"
        relative_path = Path(category) / f"{uuid4().hex}-{safe_name}"
        absolute_path = self.resolve_path(str(relative_path))
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(content)
        checksum = sha256(content).hexdigest()
        return StoredFile(
            relative_path=relative_path.as_posix(),
            absolute_path=absolute_path,
            checksum=checksum,
            size_bytes=len(content),
        )

    def delete_file(self, relative_path: str) -> None:
        path = self.resolve_path(relative_path)
        if path.exists():
            path.unlink()

    def exists(self, relative_path: str) -> bool:
        return self.resolve_path(relative_path).exists()

    def resolve_path(self, relative_path: str) -> Path:
        target = (self.root / relative_path).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("path is outside storage root")
        return target


def create_storage_backend(root: str | Path) -> LocalStorageBackend:
    return LocalStorageBackend(root=root)
```

- [ ] **Step 4: Run storage tests**

Run:

```powershell
cd backend
python -m pytest tests/test_storage.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/core/storage.py backend/tests/test_storage.py
git commit -m "feat: add local storage backend"
```

## Task 4: Confirm Business Report Imports

**Files:**
- Modify: `backend/app/schemas/imports.py`
- Create: `backend/app/services/imports/persistence.py`
- Modify: `backend/app/services/imports/orchestrator.py`
- Create: `backend/app/services/normalization/persistence.py`
- Modify: `backend/app/api/routes/imports.py`
- Create: `backend/tests/test_import_confirm.py`

- [ ] **Step 1: Write import confirm tests**

Create `backend/tests/test_import_confirm.py`:

```python
from datetime import date
from pathlib import Path

from app.core.db import create_session_factory, create_sync_engine
from app.core.storage import LocalStorageBackend
from app.domain.enums import ReportType
from app.models.base import Base
from app.models.imports import ImportJob, RawDataset, RawReportRow
from app.models.normalized import NormalizedBusinessDaily
from app.models.settings import Marketplace, Organization, SellerAccount
from app.services.imports.persistence import confirm_manual_import


def test_confirm_business_report_persists_raw_and_normalized_rows(tmp_path: Path) -> None:
    engine = create_sync_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    fixture = Path(__file__).parent / "fixtures" / "business_report.csv"

    with session_factory() as session:
        org = Organization(name="Internal Team", slug="internal")
        seller = SellerAccount(
            organization=org,
            display_name="Store A",
            amazon_seller_id="SELLER-A",
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
        session.commit()

        result = confirm_manual_import(
            session=session,
            storage=LocalStorageBackend(tmp_path),
            seller_account_id=seller.id,
            marketplace_id=marketplace.id,
            report_type=ReportType.BUSINESS_REPORT,
            date_range_start=date(2026, 5, 25),
            date_range_end=date(2026, 5, 25),
            original_filename="business_report.csv",
            file_bytes=fixture.read_bytes(),
        )
        session.commit()

        assert result.status == "succeeded"
        assert session.query(ImportJob).count() == 1
        assert session.query(RawDataset).count() == 1
        assert session.query(RawReportRow).count() == 1
        assert session.query(NormalizedBusinessDaily).count() == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_import_confirm.py -v
```

Expected: FAIL because `confirm_manual_import` does not exist.

- [ ] **Step 3: Add confirm schemas**

Add to `backend/app/schemas/imports.py`:

```python
class ImportConfirmResponse(BaseModel):
    import_job_id: int
    raw_dataset_id: int
    status: str
    row_count: int
    raw_file_checksum: str
    data_status: DataStatus
```

- [ ] **Step 4: Implement normalization persistence for business rows**

Create `backend/app/services/normalization/persistence.py`:

```python
from app.domain.enums import ReportType
from app.models.imports import RawDataset
from app.models.normalized import NormalizedBusinessDaily
from app.services.normalization.business import normalize_business_row


def persist_normalized_rows(session, dataset: RawDataset, rows: list[dict[str, str]]) -> int:
    if dataset.report_type != ReportType.BUSINESS_REPORT.value:
        return 0

    count = 0
    for row in rows:
        normalized = normalize_business_row(row)
        session.add(
            NormalizedBusinessDaily(
                raw_dataset=dataset,
                seller_account_id=dataset.seller_account_id,
                marketplace_id=dataset.marketplace_id,
                report_date=normalized.report_date,
                asin=normalized.asin,
                sku=normalized.sku,
                ordered_product_sales=normalized.ordered_product_sales,
                units_ordered=normalized.units_ordered,
                sessions=normalized.sessions,
                page_views=normalized.page_views,
                conversion_rate=normalized.conversion_rate,
                buy_box_percentage=normalized.buy_box_percentage,
            )
        )
        count += 1
    return count
```

- [ ] **Step 5: Implement confirm_manual_import**

Create `backend/app/services/imports/persistence.py`.

Behavior:

1. Save file through `LocalStorageBackend.save_upload(category="raw", filename=original_filename, content=file_bytes)`.
2. Parse saved file.
3. Detect schema.
4. Validate required columns.
5. Reject duplicate checksum for same seller, marketplace, and report type.
6. Create `ImportJob(status="succeeded")`.
7. Create `RawDataset`.
8. Create `RawReportRow` records with JSON row payloads.
9. Persist normalized rows.
10. Return `ImportConfirmResponse`.

Use `json.dumps(row, ensure_ascii=False)` for raw row JSON.

- [ ] **Step 6: Run confirm service test**

Run:

```powershell
cd backend
python -m pytest tests/test_import_confirm.py -v
```

Expected: `1 passed`.

- [ ] **Step 7: Add API route**

Modify `backend/app/api/routes/imports.py`:

- Add `seller_account_id` and `marketplace_id` to `preview_import`.
- Add `POST /api/imports/confirm`.
- Read uploaded file bytes once.
- Use `Settings().STORAGE_ROOT` and `create_storage_backend`.
- Commit the session after successful confirm.

- [ ] **Step 8: Add API test**

Extend `backend/tests/test_api_imports.py` with a confirm endpoint test that creates seller and marketplace through settings APIs, posts fixture file to `/api/imports/confirm`, and asserts:

- status code 200
- `status == "succeeded"`
- `row_count == 1`

- [ ] **Step 9: Run import API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_import_confirm.py tests/test_api_imports.py -v
```

Expected: all tests pass.

- [ ] **Step 10: Commit**

```powershell
git add backend/app/schemas/imports.py backend/app/services/imports backend/app/services/normalization/persistence.py backend/app/api/routes/imports.py backend/tests/test_import_confirm.py backend/tests/test_api_imports.py
git commit -m "feat: confirm business report imports"
```

## Task 5: Confirm Inventory and Ads Imports

**Files:**
- Modify: `backend/app/models/normalized.py`
- Modify: `backend/app/services/normalization/persistence.py`
- Modify: `backend/tests/test_import_confirm.py`

- [ ] **Step 1: Add persistence tests for inventory and ads**

Extend `backend/tests/test_import_confirm.py` with two tests:

- `test_confirm_inventory_report_persists_inventory_rows`
- `test_confirm_ads_search_term_report_persists_ads_rows`

Each test uses the existing fixtures:

```text
backend/tests/fixtures/inventory_report.csv
backend/tests/fixtures/ads_search_term_report.csv
```

Assert that `RawDataset` and `RawReportRow` records are created, and that the matching normalized table has one row.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_import_confirm.py -v
```

Expected: inventory and ads tests fail because normalized ORM tables and persistence are incomplete.

- [ ] **Step 3: Add normalized ORM tables**

Add to `backend/app/models/normalized.py`:

- `NormalizedInventoryDaily`
- `NormalizedAdsSearchTermDaily`

Each table must include:

- `raw_dataset_id`
- `seller_account_id`
- `marketplace_id`
- report date when available
- report-specific fields from the V1 dataclasses

Inventory rows may use `date_range_end` as `report_date` because Amazon inventory exports do not always include a row date.

- [ ] **Step 4: Generate migration**

Run:

```powershell
cd backend
python -m alembic revision --autogenerate -m "add v2 normalized tables"
```

Review migration to confirm it creates the two new normalized tables.

- [ ] **Step 5: Extend normalization persistence**

Modify `persist_normalized_rows`:

- For `inventory_report`, call `normalize_inventory_row`.
- For `ads_search_term_report`, call `normalize_ads_search_term_row`.
- Return persisted row count.
- Raise `ValueError("unsupported report type for normalization")` for unsupported report types.

- [ ] **Step 6: Run confirm tests**

Run:

```powershell
cd backend
python -m pytest tests/test_import_confirm.py -v
```

Expected: all import confirm tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/models/normalized.py backend/app/services/normalization/persistence.py backend/migrations/versions backend/tests/test_import_confirm.py
git commit -m "feat: persist inventory and ads imports"
```

## Task 6: Import History, Delete, and Stale Reports

**Files:**
- Create: `backend/app/services/imports/deletion.py`
- Modify: `backend/app/services/reports/repository.py`
- Modify: `backend/app/api/routes/imports.py`
- Create: `backend/tests/test_import_delete.py`

- [ ] **Step 1: Write delete behavior tests**

Create `backend/tests/test_import_delete.py`.

Test flow:

1. Create seller and marketplace.
2. Confirm a business report import.
3. Create a `DailyReport(status="active")` for the same seller, marketplace, and date.
4. Call `delete_import_job(session, storage, import_job_id)`.
5. Assert:
   - ImportJob status is `deleted`.
   - Raw file no longer exists.
   - Raw rows are deleted.
   - Normalized business rows are deleted.
   - Matching DailyReport status is `stale`.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_import_delete.py -v
```

Expected: FAIL because deletion service does not exist.

- [ ] **Step 3: Implement report repository stale function**

Create or modify `backend/app/services/reports/repository.py` with:

```python
def mark_reports_stale_for_dataset(session, dataset: RawDataset) -> int:
    """Mark reports stale when their scope and date range overlap the dataset."""
    query = session.query(DailyReport).filter(
        DailyReport.status == ReportStatus.ACTIVE.value,
        DailyReport.report_start_date <= dataset.date_range_end,
        DailyReport.report_end_date >= dataset.date_range_start,
    )
    stale_count = 0
    for report in query:
        all_store_match = report.scope_type == ReportScopeType.ALL_STORES.value
        single_store_match = (
            report.scope_type == ReportScopeType.SINGLE_STORE.value
            and report.seller_account_id == dataset.seller_account_id
            and report.marketplace_id == dataset.marketplace_id
        )
        if all_store_match or single_store_match:
            report.status = ReportStatus.STALE.value
            stale_count += 1
    return stale_count
```

Mark reports stale when:

- report scope is `all_stores`, date ranges overlap dataset date range; or
- report scope is `single_store`, seller and marketplace match, and date ranges overlap.

- [ ] **Step 4: Implement delete_import_job**

Create `backend/app/services/imports/deletion.py`.

Behavior:

- Load ImportJob and RawDataset.
- Delete raw file via storage backend.
- Delete `RawReportRow` records.
- Delete normalized records by `raw_dataset_id` from all normalized tables.
- Mark affected reports stale.
- Set ImportJob status to `deleted`.
- Set `deleted_at`.
- Leave RawDataset metadata for audit trace, but clear or keep raw_file_path as historical metadata.

- [ ] **Step 5: Add API endpoints**

Modify `backend/app/api/routes/imports.py`:

- `GET /jobs`: list newest import jobs.
- `GET /jobs/{id}`: return detail.
- `DELETE /jobs/{id}`: call `delete_import_job`.

- [ ] **Step 6: Run delete tests**

Run:

```powershell
cd backend
python -m pytest tests/test_import_delete.py -v
```

Expected: all delete tests pass.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/imports/deletion.py backend/app/services/reports/repository.py backend/app/api/routes/imports.py backend/tests/test_import_delete.py
git commit -m "feat: delete imports and mark reports stale"
```

## Task 7: Report Generation From Persisted Data

**Files:**
- Modify: `backend/app/schemas/reports.py`
- Create: `backend/app/services/reports/generator.py`
- Modify: `backend/app/services/reports/builder.py`
- Create: `backend/tests/test_report_generation_v2.py`

- [ ] **Step 1: Write report generation tests**

Create `backend/tests/test_report_generation_v2.py`.

Tests:

- `test_generate_single_store_single_day_report`
- `test_generate_all_stores_date_range_report`
- `test_generate_report_fails_without_data`

Use persisted normalized rows from in-memory SQLite and assert:

- report status is `active`
- report kind and scope are correct
- markdown and excel paths are populated
- totals include ordered product sales and units ordered

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_report_generation_v2.py -v
```

Expected: FAIL because V2 report generator does not exist.

- [ ] **Step 3: Extend report schemas**

Add to `backend/app/schemas/reports.py`:

```python
class GenerateReportRequest(BaseModel):
    scope_type: ReportScopeType
    report_kind: ReportKind
    report_start_date: date
    report_end_date: date
    seller_account_id: int | None = None
    marketplace_id: int | None = None


class DailyReportResponse(BaseModel):
    id: int
    scope_type: str
    report_kind: str
    report_start_date: date
    report_end_date: date
    status: str
    markdown: str
    excel_path: str | None
    llm_status: str
    llm_error: str | None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Implement report generator**

Create `backend/app/services/reports/generator.py`.

Behavior:

- Validate report date range.
- Validate store scope.
- Query `NormalizedBusinessDaily` rows by date range and optional seller/marketplace.
- Aggregate rows by seller/marketplace.
- Build `StoreDailySummary` values.
- Reuse `build_daily_report`, `render_daily_report_markdown`, and `write_daily_report_excel`.
- Store markdown and excel file under storage.
- Create `DailyReport`.
- Return the `DailyReport`.

V2 report generation can aggregate Business Report metrics first. Inventory and Ads data can feed warnings when available, but the first implementation must not fail if those reports are absent.

- [ ] **Step 5: Run report generation tests**

Run:

```powershell
cd backend
python -m pytest tests/test_report_generation_v2.py -v
```

Expected: all report generation tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/schemas/reports.py backend/app/services/reports/generator.py backend/app/services/reports/builder.py backend/tests/test_report_generation_v2.py
git commit -m "feat: generate reports from persisted data"
```

## Task 8: Reports API

**Files:**
- Create: `backend/app/api/routes/reports.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_reports_v2.py`

- [ ] **Step 1: Write reports API tests**

Create `backend/tests/test_api_reports_v2.py`.

Test:

- create seller/marketplace
- confirm business import
- call `POST /api/reports/generate`
- call `GET /api/reports`
- call `GET /api/reports/{id}`
- call `GET /api/reports/{id}/markdown`
- call `GET /api/reports/{id}/excel`
- assert status code 200 for each endpoint

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_api_reports_v2.py -v
```

Expected: FAIL because reports routes do not exist.

- [ ] **Step 3: Implement reports routes**

Create `backend/app/api/routes/reports.py`:

- `POST /generate`
- `GET /`
- `GET /{report_id}`
- `GET /{report_id}/markdown`
- `GET /{report_id}/excel`
- `POST /{report_id}/regenerate`

Use `FileResponse` for Excel download.

- [ ] **Step 4: Register reports router**

Modify `backend/app/main.py`:

```python
from app.api.routes.reports import router as reports_router
```

Inside `create_app`, after registering the settings router:

```python
app.include_router(reports_router, prefix="/api")
```

- [ ] **Step 5: Run reports API tests**

Run:

```powershell
cd backend
python -m pytest tests/test_api_reports_v2.py -v
```

Expected: reports API tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api/routes/reports.py backend/app/main.py backend/tests/test_api_reports_v2.py
git commit -m "feat: add reports api"
```

## Task 9: OpenAI-Compatible LLM Provider

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/services/llm/provider.py`
- Create: `backend/app/services/llm/openai_compatible.py`
- Create: `backend/tests/test_llm_openai_compatible.py`

- [ ] **Step 1: Write LLM provider tests**

Create `backend/tests/test_llm_openai_compatible.py`.

Tests:

- provider skips when API key is missing.
- provider parses OpenAI-compatible response.
- provider failure returns a controlled failure status instead of raising into report generation.

Use `httpx.MockTransport` to avoid network.

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_llm_openai_compatible.py -v
```

Expected: FAIL because provider does not exist.

- [ ] **Step 3: Extend settings**

Modify `backend/app/core/config.py`:

```python
LLM_BASE_URL: str = "https://api.openai.com/v1"
LLM_API_KEY: str | None = None
LLM_MODEL: str = "gpt-4.1-mini"
LLM_TIMEOUT_SECONDS: int = 30
```

- [ ] **Step 4: Implement provider**

Create `backend/app/services/llm/openai_compatible.py`.

Provider should:

- call `{base_url}/chat/completions`
- use bearer token auth
- send structured snapshot as JSON text
- request JSON output
- parse response text as JSON
- pass parsed output through `validate_llm_output`

Return a small result object:

```python
@dataclass(frozen=True)
class LLMAnalysisResult:
    status: str
    output: dict[str, object] | None
    error: str | None
```

- [ ] **Step 5: Run LLM tests**

Run:

```powershell
cd backend
python -m pytest tests/test_llm.py tests/test_llm_openai_compatible.py -v
```

Expected: all LLM tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/core/config.py backend/app/services/llm backend/tests/test_llm_openai_compatible.py
git commit -m "feat: add openai compatible llm provider"
```

## Task 10: Web Pages for V2 Workflow

**Files:**
- Modify: `backend/app/web/routes.py`
- Modify: `backend/app/web/templates/dashboard.html`
- Modify: `backend/app/web/templates/imports.html`
- Modify: `backend/app/web/templates/reports.html`
- Modify: `backend/app/web/templates/settings.html`
- Modify: `backend/app/web/static/app.css`
- Create: `backend/tests/test_web_v2.py`

- [ ] **Step 1: Write web route tests**

Create `backend/tests/test_web_v2.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_v2_pages_show_operational_controls() -> None:
    client = TestClient(create_app())

    pages = {
        "/": ["Recent Reports", "Stale Reports", "Recent Imports"],
        "/imports": ["Store", "Report type", "Preview", "Confirm Import", "Import History"],
        "/reports": ["All stores", "Single store", "Generate Report", "Download Excel"],
        "/settings": ["Seller Accounts", "Marketplaces", "LLM Settings"],
    }
    for path, expected_text in pages.items():
        response = client.get(path)
        assert response.status_code == 200
        for text in expected_text:
            assert text in response.text
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v2.py -v
```

Expected: FAIL because templates are still placeholders.

- [ ] **Step 3: Update templates**

Update templates to include:

- Dashboard status sections.
- Import form with seller/store fields and confirm section.
- Reports form with scope, kind, date controls, and download area.
- Settings forms for seller accounts, marketplaces, and LLM config.

Keep pages server-rendered. V2 does not need a JavaScript application.

- [ ] **Step 4: Update CSS**

Add basic table, fieldset, alert, badge, and action button styles in `backend/app/web/static/app.css`.

- [ ] **Step 5: Run web tests**

Run:

```powershell
cd backend
python -m pytest tests/test_web_v2.py tests/test_health.py -v
```

Expected: web tests pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/web backend/tests/test_web_v2.py backend/tests/test_health.py
git commit -m "feat: add v2 internal workflow pages"
```

## Task 11: Full V2 Integration Verification

**Files:**
- Modify: docs only if verification exposes missing run instructions after V2 implementation

- [ ] **Step 1: Run lint**

Run:

```powershell
cd backend
python -m ruff check .
```

Expected: `All checks passed!`

- [ ] **Step 2: Run full test suite**

Run:

```powershell
cd backend
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Verify Docker Postgres migration**

Run:

```powershell
cd C:\Users\user01\shuju-agent
docker compose up -d postgres
docker compose exec -T postgres pg_isready -U copilot -d copilot
cd backend
python -m alembic upgrade head
python -m alembic current
```

Expected:

- Postgres accepts connections.
- Alembic reaches latest head.

- [ ] **Step 4: Verify local app endpoints**

Start app:

```powershell
cd C:\Users\user01\shuju-agent\backend
python -m uvicorn app.main:app --reload --port 8000
```

In another shell verify:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/settings/store-options
Invoke-RestMethod http://127.0.0.1:8000/api/imports/jobs
Invoke-RestMethod http://127.0.0.1:8000/api/reports
```

Expected: each endpoint returns a successful response.

- [ ] **Step 5: Stop Docker**

Run:

```powershell
cd C:\Users\user01\shuju-agent
docker compose down
```

- [ ] **Step 6: Commit verification fixes if any**

If verification required code or docs changes:

```powershell
git add backend docs
git commit -m "fix: resolve v2 verification issues"
```

If no files changed, do not create a commit.

## Self-Review

Spec coverage:

- Store configuration: Task 2 and Task 10.
- Store option equals `SellerAccount + Marketplace`: Task 2.
- Single-day and date-range report: Task 7 and Task 8.
- Single-store and all-stores report: Task 7 and Task 8.
- Confirm imports: Task 4 and Task 5.
- Raw file storage: Task 3 and Task 4.
- Raw rows and normalized rows: Task 4 and Task 5.
- Delete import and stale reports: Task 6.
- Synchronous report generation: Task 7 and Task 8.
- OpenAI-compatible LLM: Task 9.
- Four V2 pages: Task 10.
- Final lint, tests, migration, and local run: Task 11.

Placeholder scan:

- The plan intentionally keeps implementation exact at the task boundary.
- No task depends on Amazon SP-API or Ads API credentials.
- No task introduces auth, queues, or push notifications.

Type consistency:

- `scope_type` values are `single_store` and `all_stores`.
- `report_kind` values are `single_day` and `date_range`.
- `ReportStatus` values are `active`, `stale`, and `failed`.
- Import status values include `previewed`, `succeeded`, `failed`, and `deleted`.
