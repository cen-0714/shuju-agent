# Amazon Daily Copilot MVP Design

## Purpose

Build an internal Amazon store analytics Copilot for multiple company-owned seller accounts. The MVP focuses on a daily operating report for the Americas region, while keeping the data model ready for future expansion to Europe, Japan, and other marketplaces.

The system is not an automatic Amazon operations agent. It collects data, normalizes reports, computes metrics, detects obvious anomalies, prepares LLM-ready snapshots, generates daily reports, and delivers those reports for human review. It must not automatically change listings, prices, ads, bids, budgets, negative keywords, or any other Amazon account setting.

## Current Constraints

- The system is for internal use only, not a customer-facing SaaS product.
- There are multiple company-owned Amazon stores.
- The first production scope is the Americas region.
- Future regions must be supported without redesigning the database or report pipeline.
- SP-API and Amazon Ads API credentials are not available yet.
- Users can log in to Seller Central and Amazon Ads Console.
- Users do not yet have a reliable manual export workflow.
- The MVP must avoid buyer PII and sensitive buyer-level data.

## Recommended Approach

Use an API-ready manual import MVP.

The first working version uses uploaded Seller Central and Amazon Ads report files. At the same time, the data source boundary is designed as an adapter interface, so future SP-API and Amazon Ads API integrations feed the same raw dataset pipeline instead of bypassing or replacing the core system.

```text
ManualFileAdapter    -> RawDataset
SPAPIReportAdapter   -> RawDataset
AdsAPIReportAdapter  -> RawDataset

RawDataset -> NormalizedDataset -> Metrics -> DailyReport -> LLM Summary
```

Only `ManualFileAdapter` is implemented in the MVP. `SPAPIReportAdapter` and `AdsAPIReportAdapter` are defined as future adapters with the same output contract.

## Product Scope

### In Scope

- Manage multiple internal seller accounts.
- Manage marketplaces under each seller account.
- Support Americas-region marketplaces first.
- Upload daily or recent-period report files.
- Validate report type, required columns, seller account, marketplace, and date range.
- Store raw uploaded files and import metadata.
- Normalize report rows into internal tables.
- Compute daily sales, traffic, ad, and inventory metrics.
- Generate a multi-store daily report.
- Generate per-store report sections.
- Generate a structured LLM snapshot from computed metrics.
- Use the LLM to explain trends, anomalies, risks, and recommended human actions.
- Store report versions with data, metric, prompt, and model versions.
- Provide a basic internal web UI for dashboard, imports, reports, and settings.

### Out of Scope

- Public SaaS tenant onboarding.
- Customer billing, external organizations, or complex customer roles.
- Automatic listing edits.
- Automatic price changes.
- Automatic bid, budget, targeting, or negative keyword changes.
- Buyer PII ingestion or analysis.
- Buyer messages, addresses, phone numbers, emails, or payment data.
- Profit-accurate financial accounting.
- Deep PPC optimization.
- Full BI exploration.
- Crawling as a core data source.

## MVP Report Inputs

The MVP supports a small set of report categories. Exact column mappings can vary by export format, so the importer must store a schema version for each mapping.

### Business Reports

Purpose: sales and traffic performance.

Initial supported use:

- Daily store-level sales and traffic.
- ASIN or child item sales and traffic where available.
- Sessions, page views, units ordered, ordered product sales, conversion rate, and buy box percentage when present.

### Inventory Reports

Purpose: inventory visibility and risk detection.

Initial supported use:

- Active listing inventory.
- SKU, ASIN, fulfillment channel, available quantity, listing status, and price when present.
- Simple low-stock and inactive-listing flags.

### Ads Reports

Purpose: advertising efficiency summary.

Initial supported use:

- Sponsored Products campaign, targeting, or search term reports.
- Spend, impressions, clicks, CPC, sales, orders, ACOS, ROAS, CTR, and CVR when present.
- High-spend low-return flags and search-term waste hints.

## Data Model Principles

The database keeps internal multi-store support but does not implement full SaaS complexity.

Core dimensions:

- `organization`: one internal company organization.
- `seller_account`: each company-owned Amazon seller account.
- `marketplace`: region, marketplace id, country, timezone, and currency.
- `data_source`: manual upload, SP-API, Ads API, or future third-party source.
- `report_type`: business report, inventory report, ads campaign report, ads targeting report, ads search term report.

Every imported dataset must include:

- `seller_account_id`
- `marketplace_id`
- `region`
- `source`
- `report_type`
- `date_range_start`
- `date_range_end`
- `schema_version`
- `raw_file_path`
- `raw_file_checksum`
- `ingested_at`
- `data_status`
- `data_version`

The MVP uses three data layers:

- Raw layer: original files, parsed rows, import metadata, and validation results.
- Normalized layer: cleaned business rows with consistent seller account, marketplace, date, currency, ASIN, SKU, campaign, and search term fields.
- Metrics layer: code-calculated metrics used by dashboards, reports, and LLM snapshots.

LLM output must never be the source of truth for key metrics.

## Data Freshness

The MVP must treat Amazon data as delayed and revisable.

Supported statuses:

- `preliminary`: same-day or newly uploaded data that may change.
- `stable`: T+1 or T+2 data suitable for daily reporting.
- `final`: older data suitable for review and trend analysis.

Reports must display data freshness when the report uses preliminary or stable data. Ads sales, orders, ACOS, ROAS, search terms, refunds, and financial metrics are especially likely to change after first availability.

## Import Flow

1. User opens Data Import.
2. User selects seller account, marketplace, report type, and date range.
3. User uploads CSV or Excel file.
4. System stores the file in object storage or local file storage.
5. System computes file checksum and checks for duplicate imports.
6. System parses headers and detects mapping schema.
7. System validates required columns.
8. System previews row count, detected dates, detected currency, and sample rows.
9. User confirms import.
10. System writes raw import records.
11. System normalizes rows.
12. System computes affected metrics.
13. System marks the import job as succeeded or failed with a typed error.

## API-Ready Adapter Contract

Manual uploads and future APIs must output the same logical raw dataset envelope.

```text
RawDataset
  dataset_id
  seller_account_id
  marketplace_id
  region
  source
  report_type
  date_range_start
  date_range_end
  schema_version
  raw_file_path
  raw_file_checksum
  row_count
  data_status
  source_generated_at
  ingested_at
  import_job_id
```

Future API adapters must not write directly to normalized or metrics tables. They must create raw datasets first, then reuse the same normalization and metric processing pipeline as manual uploads.

## Metrics Scope

The MVP focuses on daily operating metrics.

Sales and traffic:

- ordered product sales
- units ordered
- sessions
- page views
- conversion rate
- unit session percentage when present
- buy box percentage when present

Ads:

- impressions
- clicks
- spend
- attributed sales
- attributed orders
- CPC
- CTR
- CVR
- ACOS
- ROAS

Inventory:

- available quantity
- inactive listing flag
- low-stock flag
- simple days-of-cover when sales velocity is available

Derived health flags:

- sales dropped sharply
- traffic dropped sharply
- conversion dropped sharply
- ad spend increased without sales lift
- high spend with low or zero orders
- low inventory
- inactive listing
- missing report data

Metric definitions must have names, formulas, source fields, time grain, currency rule, and version. The first version can be stored as seeded application configuration.

## Daily Report

The MVP daily report contains:

- Executive summary.
- Multi-store totals.
- Store-by-store sales and ad summary.
- Top positive changes.
- Top negative changes.
- Inventory risk section.
- Advertising waste section.
- Missing or stale data warnings.
- LLM interpretation.
- Suggested human actions.
- Data freshness and report version metadata.

The first report formats are:

- JSON for internal storage.
- Markdown for web display.
- Excel for operator download.

PDF can be added after the Markdown and Excel report structure is stable.

## LLM Analysis Design

The LLM receives a compact structured snapshot, not raw CSV files or raw API responses.

Snapshot contents:

- report metadata
- seller accounts included
- marketplaces included
- data freshness summary
- metric definitions used
- aggregate metrics
- per-store metric summaries
- flagged anomalies
- selected ASIN, campaign, or search term highlights

The LLM must output structured JSON with:

- summary
- findings
- evidence references
- possible causes
- recommended human actions
- risk level
- confidence
- human review required flag

The output validator must check:

- JSON schema validity.
- Evidence references exist in the snapshot.
- Numeric values are not invented.
- Recommendations do not suggest automatic Amazon account changes.
- No buyer PII appears.

## Web UI

The MVP UI has four pages.

### Dashboard

Shows the latest daily report, multi-store totals, store status, data freshness warnings, and top anomalies.

### Data Import

Supports file upload, report type selection, validation preview, import history, error messages, and re-import flow.

### Report Center

Shows report history, report status, report versions, Markdown view, Excel download, and regeneration action.

### Settings

Supports internal organization settings, seller accounts, marketplaces, report type mappings, LLM provider settings, and delivery settings.

## Error Handling

Manual import errors:

- unsupported file type
- unreadable file
- missing required columns
- unknown schema
- seller account mismatch
- marketplace mismatch
- date range mismatch
- duplicate file
- duplicate dataset
- empty dataset
- normalization failure
- metric calculation failure

Future API errors:

- authorization expired
- permission denied
- rate limited
- temporary provider failure
- report not ready
- report cancelled
- report expired
- schema changed
- partial dataset

Errors must be stored on import or sync job records and displayed in Data Import or future Data Sync pages.

## Security

- Do not ingest buyer names, addresses, phone numbers, emails, messages, or payment data.
- Do not send secrets, tokens, raw files, or buyer-level data to the LLM.
- Store API keys and tokens in environment variables or a secret manager.
- Redact secrets in logs.
- Record audit logs for uploads, imports, report generation, and future API credential changes.
- Internal access can start with a simple administrator/operator split.

## Testing Strategy

MVP tests must cover:

- CSV and Excel upload parsing.
- Header mapping for each supported report type.
- Missing-column validation.
- Duplicate checksum detection.
- Raw dataset creation.
- Normalization for sample business, inventory, and ads reports.
- Metric calculations for sales, ads, and inventory.
- Data freshness classification.
- Daily report JSON generation.
- Markdown report rendering.
- Excel report generation.
- LLM snapshot building.
- LLM output schema validation.
- Policy validation against unsafe recommendations.

Future API adapter tests must verify that SP-API and Ads API adapters create the same `RawDataset` envelope used by manual uploads.

## Phased Delivery

### Phase 1: Project Foundation

Create the repository structure, backend service, database migrations, background job model, internal configuration, and basic health checks.

### Phase 2: Manual Import Pipeline

Implement Data Import, raw file storage, schema detection, validation preview, raw dataset creation, normalization, and import history.

### Phase 3: Metrics and Daily Report

Implement metric definitions, metric calculation, anomaly flags, daily report generation, Markdown display, and Excel download.

### Phase 4: LLM Copilot Summary

Implement snapshot building, prompt orchestration, LLM provider adapter, JSON schema validation, evidence validation, and safe recommendation checks.

### Phase 5: Internal Delivery

Add report center polish, delivery settings, and optional Feishu or DingTalk summary push with report links.

### Phase 6: API Readiness and Integration

Prepare SP-API and Ads API application setup, callback URL, credential storage, target report type matrix, sync job records, rate limit handling, and adapter implementation. API adapters must feed the existing raw dataset pipeline.

## Acceptance Criteria

The MVP is complete when:

- Multiple seller accounts can be configured.
- At least one Americas marketplace can be configured per seller account.
- Users can upload business, inventory, and ads report files.
- Imports are validated before confirmation.
- Duplicate files are rejected or handled idempotently.
- Raw files and raw dataset metadata are stored.
- Normalized rows are created from accepted imports.
- Daily metrics are calculated from normalized data.
- A multi-store daily report is generated.
- The report includes data freshness warnings.
- The report can be viewed as Markdown.
- The report can be downloaded as Excel.
- The LLM summary is generated from a structured snapshot.
- The LLM output passes JSON schema and policy validation before display.
- Unsafe automatic-operation recommendations are rejected or marked invalid.
- The data source adapter contract is documented and ready for future SP-API and Ads API adapters.
