# Amazon API Readiness Checklist

## SP-API

- Create or confirm Amazon Developer profile.
- Use private app path for internal company use.
- Configure Login With Amazon credentials.
- SP-API no longer requires AWS IAM role/policy or AWS Signature Version 4 as of 2023-10-02; use LWA access token.
- Do not configure public OAuth callback URLs for this internal self-authorization path.
- Store refresh tokens encrypted and outside source control.
- Exclude buyer PII roles.
- Implement 401 and 403 handling as permission-denied job errors.
- Implement 429 handling as rate-limited job errors with retry-after awareness.

## V5 Permission Boundary

Allowed Amazon roles based on the current app request:

- 商品信息
- 定价
- 亚马逊物流配送买家, only non-PII fulfillment statistics
- 洞察销售伙伴
- 财务与会计核算
- 库存和订单追踪
- 亚马逊物流
- 品牌分析

Blocked roles:

- 买家沟通
- 招揽买家
- 可持续认证
- 亚马逊仓储和分拨
- 账户信息服务提供商
- 发起付款服务提供商
- 直接向消费者配送
- 税务发票
- 税务汇款
- 专业服务

## V5 Report Scope

Initial enabled report:

- `business_sales_traffic -> GET_SALES_AND_TRAFFIC_REPORT`

Registered but disabled until parser and normalization are implemented:

- `open_listings -> GET_FLAT_FILE_OPEN_LISTINGS_DATA`
- `all_listings -> GET_MERCHANT_LISTINGS_ALL_DATA`

Reports API data is raw report data. Every downloaded report must pass through:

```text
SPAPISyncJob
-> ImportJob(source="sp_api")
-> RawDataset
-> RawReportRows
-> Normalized tables
-> Report/LLM snapshot/Excel
```

API adapters must not write directly to normalized or metrics tables.

## Amazon Ads API

Ads API is out of V5 scope.

Future Ads API readiness still requires:

- Apply for Amazon Ads API access.
- Record client id and client secret outside source control.
- Confirm profiles for each seller account and marketplace.
- Map Sponsored Products campaign, targeting, and search term reports to internal report types.
- Route downloaded report files through the same raw dataset and normalization pipeline as manual uploads.

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
- import_job_id

For SP-API, `spapi_sync_jobs.import_job_id` points to the `ImportJob` created after the report document is downloaded and ingested.
