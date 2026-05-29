# Amazon Daily Copilot V5 SP-API 与 AI 报告管线设计

## 目标

V5 的目标是把项目从“手动导入 + 本地日报”推进到“可手动触发的 SP-API 报表同步 + 数据清洗 + AI 分析 + Excel 输出”。这是内部自用系统，不做 SaaS，不接外部卖家授权，不做买家 PII，不做自动定时同步。

V5 必须解决这些问题：

- 用户可以在页面选择店铺和市场，而不是手填 `seller_account_id`、`marketplace_id`。
- 系统可以用 V4 保存的 Amazon 自授权 refresh token 换取 LWA access token。
- 系统可以按白名单报表类型创建 Reports API 同步任务，轮询、下载、保存原始报表文件。
- SP-API 下载的数据必须进入现有 RawDataset/RawReportRows/Normalized 数据管线，不允许绕过原始数据层直接生成指标。
- Amazon 原始数据要先清洗成结构化指标，再生成给大模型看的快照。
- Prompt 必须版本化，LLM 输出必须是结构化 JSON，并经过后端校验。
- Excel 必须由代码生成，不允许让大模型直接生成 Excel 文件。

## 约束与非目标

### 业务边界

- 只服务我们自己的 Amazon 店铺。
- 多店铺是内部多账号，不是外部卖家入驻。
- 当前优先美洲站，数据模型必须支持后续扩展欧洲、日本等区域。
- 不做买家 PII 数据。
- 不做自动定时同步。
- 不做 Amazon Ads API。
- 不做自动改价、自动改 Listing、自动操作库存、自动发货等写操作。
- 不做 Amazon Appstore、外部授权 callback、公开 SaaS 授权流程。

### 技术边界

- V5 只做手动点击触发的同步任务。
- V5 可以实现同步任务状态机，但不引入 Celery/RQ/后台队列。
- V5 不要求一次接完所有已勾选角色对应的所有 API。角色是权限边界，不是实现承诺。
- 每个对外开放的报表类型必须先进入报表类型注册表，写明 Amazon `reportType`、所需角色、输出格式、解析器版本、规范化版本和当前状态。

## 已勾选权限白名单

根据用户在 Amazon 后台勾选的角色，V5 只允许设计和暴露以下数据范围：

| Amazon 后台角色 | V5 使用方式 |
| --- | --- |
| 商品信息 | 可作为 Listing/Catalog 类数据来源候选，不做写入 Listing |
| 定价 | 可作为价格和 Listing 报表来源候选，不做自动改价 |
| 亚马逊物流配送买家 | 仅允许非 PII 的配送/履约统计类数据候选 |
| 洞察销售伙伴 | 可作为业务洞察类数据候选 |
| 财务与会计核算 | 可作为 settlement/finance 报表候选 |
| 库存和订单追踪 | 可作为库存、Listing、订单汇总类报表候选 |
| 亚马逊物流 | 可作为 FBA 库存和履约统计候选 |
| 品牌分析 | 作为 V5 首个正式实现的数据入口，优先接 `GET_SALES_AND_TRAFFIC_REPORT` |

未勾选角色默认禁止：

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

接口和页面不得展示这些未勾选角色的数据入口。后续如果 Amazon 后台重新授权，需要先更新此规格或后续规格，再进入开发。

## 官方文档事实

截至 2026-05-29，V5 设计按 Amazon 官方文档中的这些事实执行：

- SP-API 自 2023-10-02 起不再要求 AWS IAM 或 AWS Signature Version 4，请求仍使用 LWA access token。来源：[SP-API no longer requires AWS IAM or AWS Signature Version 4](https://developer-docs.amazon.com/sp-api/lang-tr_TR/changelog/sp-api-will-no-longer-require-aws-iam-or-aws-signature-version-4)。
- Reports API v2021-06-30 包含 `createReport`、`getReport`、`getReportDocument` 等操作。来源：[Reports v2021-06-30 Reference](https://developer-docs.amazon.com/sp-api/reference/reports-v2021-06-30)。
- `GET_SALES_AND_TRAFFIC_REPORT` 属于 Sales and Traffic Business Report，角色是 Brand Analytics，输出 JSON，包含销售表现和流量指标。来源：[Analytics Reports](https://developer-docs.amazon.com/sp-api/lang-US/docs/report-type-values-analytics)。
- `GET_FLAT_FILE_OPEN_LISTINGS_DATA` 输出 tab 分隔文本，包含 SKU、ASIN、价格、数量等 Listing 汇总字段。来源：[Inventory Reports](https://developer-docs.amazon.com/sp-api/lang-US/docs/report-type-values-inventory)。

因此，`docs/api-readiness/amazon-api-readiness.md` 在 V5 需要同步修正：不能再把 AWS IAM role/policy 和 SigV4 作为必填前置项。

## 方案选择

### 方案 A：先打通 Business Report，再扩展报表注册表

先正式实现 `GET_SALES_AND_TRAFFIC_REPORT`，因为它直接服务日报、AI 分析和 Excel 输出；其他已勾选角色只进入注册表或禁用候选，不在页面开放运行。

优点：最快形成可测试闭环，数据能直接进入现有 `NormalizedBusinessDaily` 和日报模块。缺点：财务、库存、FBA 不会在 V5 第一阶段全部可用。

### 方案 B：一次接多个 Reports API 报表

同时实现销售、库存、Listing、财务报表。

优点：覆盖面大。缺点：解析器、字段清洗、权限错误、报表差异会同时爆炸，不适合当前阶段。

### 方案 C：先只做 SP-API 原始下载，不接 AI 和 Excel

先把报表文件下载回来，后续再做分析。

优点：风险低。缺点：不能解决用户真正要的“点击生成分析和 Excel”目标。

V5 采用方案 A：先打通 `GET_SALES_AND_TRAFFIC_REPORT` 的完整闭环，同时建立注册表和边界，让后续版本按模块扩展。

## 报表类型注册表

新增后端静态注册表，路径建议：

```text
backend/app/services/amazon/report_types.py
```

每个报表类型必须包含：

```text
internal_report_type
amazon_report_type
display_name
role_group
source
output_format
parser_version
normalizer_version
status
pii_risk
notes
```

V5 初始注册表：

| internal_report_type | amazon_report_type | 状态 | 说明 |
| --- | --- | --- | --- |
| `business_sales_traffic` | `GET_SALES_AND_TRAFFIC_REPORT` | `enabled` | V5 首个正式同步报表，Brand Analytics，JSON |
| `open_listings` | `GET_FLAT_FILE_OPEN_LISTINGS_DATA` | `disabled` | Listing/库存/价格候选，后续实现解析 |
| `all_listings` | `GET_MERCHANT_LISTINGS_ALL_DATA` | `disabled` | Listing 候选，后续实现解析 |

页面只能展示 `status = enabled` 的报表类型。后端也必须校验，不能靠前端隐藏。

财务和 FBA 报表不进入 V5 初始注册表。它们只作为后续发现清单保留，必须先确认具体 Amazon `reportType`、输出格式、字段含义和非 PII 边界，再进入新版本开发。

## SP-API 同步流程

V5 同步流程：

```text
选择店铺/市场
-> 选择已启用 report type
-> 选择日期范围
-> 创建 spapi_sync_jobs
-> 用 refresh token 换 LWA access token
-> 调用 Reports API createReport
-> 轮询 getReport
-> 完成后调用 getReportDocument
-> 下载原始报表文件
-> 保存到 storage/raw/spapi/...
-> 建立 ImportJob(source=sp_api)
-> 建立 RawDataset + RawReportRows
-> 运行对应 parser 和 normalizer
-> 写入 normalized tables
-> 标记同步任务完成
```

重要约束：

- `spapi_sync_jobs` 记录 Amazon 报表生命周期。
- `ImportJob` 继续作为数据入库生命周期记录。
- `RawDataset.import_job_id` 不在 V5 改成 nullable。SP-API 下载完成后创建 `ImportJob(source = "sp_api")`，再复用现有 RawDataset 关系。
- `spapi_sync_jobs.import_job_id` 在入库完成后指向对应 ImportJob。
- 这样可以复用手动上传的解析、去重、原始文件保存和规范化管线，减少数据库破坏性迁移。

## 数据模型

新增模型 `SPAPISyncJob`：

```text
id
seller_account_id
marketplace_id
amazon_authorization_id
import_job_id
internal_report_type
amazon_report_type
date_range_start
date_range_end
report_options_json
status
amazon_report_id
amazon_report_document_id
download_path
error_code
error_message
requested_at
completed_at
created_at
updated_at
```

状态枚举：

```text
draft
requested
processing
download_ready
downloaded
imported
failed
cancelled
```

错误分类：

```text
missing_authorization
lwa_token_failed
permission_denied
rate_limited
amazon_report_failed
download_failed
parse_failed
normalize_failed
duplicate_dataset
unexpected_error
```

## 数据清洗

Reports API 不负责把数据清洗成系统指标，也不会自动变成大模型能稳定理解的数据。V5 明确分四层：

1. 原始文件层  
   保存 Amazon 返回的 JSON 或 flat file，不改写内容。记录 checksum、文件路径、原始大小、下载时间。

2. 原始行层  
   将 JSON 数组或 flat file 行转成 RawReportRows。未知字段保留在 `row_json`。

3. 规范化指标层  
   将可识别字段转成业务指标表，例如 `NormalizedBusinessDaily`。金额、数量、日期、币种、店铺、市场必须类型化。

4. LLM 快照层  
   只把规范化后的摘要、趋势、异常、数据缺口、证据引用交给大模型。不把原始 token、原始文件路径、未清洗字段直接给大模型。

未知字段处理：

- 保存到 schema profile。
- 不阻断导入，除非缺少必需字段。
- 记录 warning，进入报告和 Excel。

## LLM Prompt 与输出规范

Prompt 不再写死在 `openai_compatible.py`。V5 新增版本化 Prompt：

```text
backend/app/services/llm/prompts/daily_report_v1/system.md
backend/app/services/llm/prompts/daily_report_v1/user.md
backend/app/services/llm/prompt_registry.py
```

Prompt registry 必须记录：

```text
prompt_version
output_schema_version
system_prompt_path
user_prompt_path
allowed_report_kinds
```

LLM 输入：

- 使用 `build_llm_snapshot()` 生成。
- 快照必须包含 `evidence_ids`。
- 每个 store summary、趋势、warning 都必须能映射到 evidence id。

LLM 输出必须符合 Pydantic schema：

```json
{
  "summary": "string",
  "findings": [
    {
      "title": "string",
      "severity": "info|warning|critical",
      "evidence_refs": ["string"],
      "reasoning": "string",
      "recommended_human_actions": ["string"],
      "human_review_required": true
    }
  ],
  "data_quality_notes": ["string"]
}
```

校验规则：

- `summary` 必须存在。
- `findings` 必须是数组。
- 每个 `evidence_refs` 必须来自快照中的 `evidence_ids`。
- 每个 finding 必须 `human_review_required = true`。
- 禁止出现自动操作建议，例如自动改价、自动改 Listing、自动暂停活动、自动修改库存。
- LLM 失败不阻断报告生成，报告状态记录 `llm_status = failed`，Excel 增加 AI 失败说明。

## Excel 输出

Excel 由后端代码生成，LLM 只提供经过校验的结构化 JSON。

V5 Excel sheet：

| Sheet | 来源 | 说明 |
| --- | --- | --- |
| Overview | DailyReportDocument | 总览、日期范围、店铺范围、核心指标 |
| Store Summary | NormalizedBusinessDaily 聚合 | 每店铺销售、订单、单位数、数据状态 |
| AI Insights | 校验后的 LLM JSON | 摘要、发现、严重程度、证据引用 |
| Action Checklist | 校验后的 LLM JSON | 只放人工复核动作 |
| Data Warnings | parser/normalizer/report warnings | 字段缺失、未知字段、数据延迟、重复导入 |
| Sync Jobs | SPAPISyncJob/RawDataset | 报表类型、Amazon report id、下载时间、checksum |

Excel 不直接暴露 refresh token、LWA access token、client secret、TOKEN_ENCRYPTION_KEY。

## 页面设计

V5 页面优先做可操作闭环，不做复杂 BI。

### 背景设定

- 显示 Seller Accounts 列表。
- 显示 Amazon 授权状态。
- Marketplace 表单改为选择 seller account，不要求用户手填内部 id。
- 自授权表单改为选择 seller account，并自动带出卖家记号。

### 数据同步

新增页面或导航项：

```text
SP-API 同步
```

控件：

- 店铺/市场下拉，来自 `GET /api/settings/store-options`。
- 报表类型下拉，只显示 enabled report types。
- 日期范围选择。
- “创建并运行同步”按钮。
- 同步任务列表，显示状态、Amazon report id、错误原因、入库结果。
- “刷新状态”按钮，手动推进轮询，不做自动定时。

### 数据导入

手动导入页面继续保留，但店铺选择改为下拉，不再让用户手填内部 id。

### 报告中心

报告生成页面改为：

- 选择单店铺或全部店铺。
- 选择日期范围。
- 生成报告。
- 展示 Markdown。
- 下载 Excel。
- 显示 LLM 状态和数据来源。

## API 设计

新增 API：

```text
GET /api/spapi/report-types
GET /api/spapi/sync-jobs
POST /api/spapi/sync-jobs
GET /api/spapi/sync-jobs/{sync_job_id}
POST /api/spapi/sync-jobs/{sync_job_id}/run
POST /api/spapi/sync-jobs/{sync_job_id}/refresh
```

`POST /api/spapi/sync-jobs` 请求：

```json
{
  "seller_account_id": 1,
  "marketplace_id": 1,
  "internal_report_type": "business_sales_traffic",
  "date_range_start": "2026-05-20",
  "date_range_end": "2026-05-20",
  "report_options": {
    "dateGranularity": "DAY",
    "asinGranularity": "SKU"
  }
}
```

后端校验：

- seller account 必须存在。
- marketplace 必须属于 seller account。
- 必须存在 active AmazonAuthorization。
- report type 必须是 enabled。
- 日期范围必须合法。
- `GET_SALES_AND_TRAFFIC_REPORT` 默认 `dateGranularity = DAY`，`asinGranularity = SKU`。

## 客户端与服务拆分

建议文件结构：

```text
backend/app/services/amazon/reports_client.py
backend/app/services/amazon/report_types.py
backend/app/services/amazon/sync_jobs.py
backend/app/services/amazon/report_downloads.py
backend/app/services/imports/spapi_ingestion.py
backend/app/services/llm/prompt_registry.py
backend/app/services/llm/output_schema.py
backend/app/services/llm/prompts/daily_report_v1/system.md
backend/app/services/llm/prompts/daily_report_v1/user.md
backend/app/api/routes/spapi.py
```

职责：

- `reports_client.py` 只负责 HTTP 调用 Amazon Reports API。
- `report_types.py` 只负责白名单和 report type 元数据。
- `sync_jobs.py` 负责状态机和数据库记录。
- `report_downloads.py` 负责下载文件和保存。
- `spapi_ingestion.py` 负责把 SP-API 文件送入现有 ImportJob/RawDataset 管线。
- `prompt_registry.py` 负责加载版本化 Prompt。
- `output_schema.py` 负责 LLM 输出 Pydantic schema。
- `spapi.py` 只做 API 入参校验和调用服务。

## 测试策略

测试必须使用 mock transport，不允许在自动测试中调用真实 Amazon。

需要覆盖：

- report type registry 只返回 enabled 报表。
- 未勾选角色对应的 report type 不在 API 返回。
- 没有 active authorization 时创建 sync job 失败。
- refresh token 可以换取 LWA access token。
- Reports API createReport/getReport/getReportDocument 的成功流程。
- 401/403 转为 `permission_denied`。
- 429 转为 `rate_limited`，记录 retry-after。
- Amazon report 失败转为 `amazon_report_failed`。
- 下载后的文件会保存到 storage。
- SP-API 下载会创建 `ImportJob(source = "sp_api")` 和 RawDataset。
- `GET_SALES_AND_TRAFFIC_REPORT` parser 能写入 `NormalizedBusinessDaily`。
- LLM prompt registry 能加载 `daily_report_v1`。
- LLM 输出 schema 能拒绝缺少 evidence 的结果。
- LLM 输出 schema 能拒绝自动操作建议。
- Excel 包含 Overview、Store Summary、AI Insights、Action Checklist、Data Warnings、Sync Jobs。

## 验收标准

- 用户能在页面看到 `hrm - US` 这类店铺/市场选项。
- 用户不需要手填 `seller_account_id` 或 `marketplace_id`。
- 用户能看到 Amazon 自授权是否已绑定到店铺。
- 用户只能选择 V5 启用的 `business_sales_traffic` 报表。
- 用户点击后能创建 SP-API 同步任务。
- 同步任务能记录 Amazon report id、状态、错误原因。
- 下载的原始报表文件保存在后端 storage。
- 下载数据进入 RawDataset 和 RawReportRows。
- 首个支持的 Business Report 能写入 `NormalizedBusinessDaily`。
- 报告中心能用 SP-API 导入的数据生成 Markdown 和 Excel。
- LLM Prompt 来自版本化文件，不再硬编码在 provider 中。
- LLM 输出是 schema 校验后的 JSON。
- Excel 由代码生成，并包含 AI Insights 和 Action Checklist。
- 未勾选角色的数据入口不会出现在页面或 API。
- 不需要公共域名 callback。
- 不需要 AWS IAM role/policy 或 SigV4。
- 不做买家 PII。
- 不做自动定时同步。

## 后续版本

V6 可以在 V5 管线稳定后扩展：

- 启用 Listing/库存类报表解析。
- 启用财务/Settlement 报表解析。
- 增加 FBA 库存与履约统计。
- 增加人工触发的多店铺批量同步。
- 引入后台队列和定时任务。
- 引入 Amazon Ads API。
