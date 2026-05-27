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
