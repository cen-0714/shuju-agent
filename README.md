# Amazon Daily Copilot

内部使用的 Amazon 多店铺日常运营数据分析工具。当前版本支持手动导出文件导入、SP-API 手动同步、数据落库、AI 分析报告和 Excel 输出。

## 当前功能

- 店铺配置：维护 `Seller Account + Marketplace`，支持美洲站基础市场信息。
- 手动导入：支持 Business Report、Inventory Report、Ads Search Term Report 的 CSV/XLSX 预览与确认导入。
- 数据持久化：保存原始文件、原始行、标准化后的业务/库存/广告搜索词数据；Orders 原始层仅用于内部对账和重算。
- 导入删除：删除导入会移除原始文件和相关明细数据，并把受影响报告标记为 `stale`。
- 报告生成：支持单店铺/全部店铺、单日/日期范围报告，可选数据源（订单 / 销售流量）。
- 订单销售趋势：基于 SP-API 全部订单报表，输出日/周/月销售趋势和 SKU 表现，多币种分列。
- 报告下载：支持 Markdown 查看和 Excel 下载，Excel 包含 Sales Trend、SKU Performance、AI Insights、Action Checklist、Data Warnings、Sync Jobs。
- LLM 分析：支持 OpenAI-compatible 接口；Prompt 按版本文件管理，输出按 JSON schema 校验。
- Amazon SP-API 自授权：支持录入 Amazon 后台生成的 refresh token，并加密保存。
- SP-API 同步：支持手动创建并运行 `GET_SALES_AND_TRAFFIC_REPORT` 和 `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` 同步任务，下载后进入 RawDataset 和标准化管线。
- 页面入口：Dashboard、Data Import、SP-API Sync、Report Center、Settings 五个服务端页面。

暂未实现：自动定时同步、后台异步任务队列、Ads API 自动拉取、登录权限、推送通知、Orders raw 脱敏/保留期策略、Amazon 写操作。

## 环境要求

- Windows PowerShell
- Python 3.12+
- Docker Desktop
- Git

## 首次启动

在项目根目录执行：

```powershell
@"
DATABASE_URL=postgresql+psycopg://copilot:copilot@localhost:5432/copilot
STORAGE_ROOT=storage
LLM_PROVIDER=mock
"@ | Set-Content -Encoding UTF8 backend\.env

cd backend
python -m pip install -e ".[dev]"
cd ..
docker compose up -d postgres
cd backend
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --port 8000
```

打开：

- 页面入口：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health
- Amazon SP-API 自授权配置状态：http://127.0.0.1:8000/api/auth/amazon/status

## 常用命令

启动数据库：

```powershell
docker compose up -d postgres
```

停止数据库：

```powershell
docker compose down
```

执行数据库迁移：

```powershell
cd backend
python -m alembic upgrade head
```

启动后端：

```powershell
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

运行测试：

```powershell
cd backend
python -m pytest -q
```

运行 lint：

```powershell
cd backend
python -m ruff check .
```

## 基础使用流程

建议优先使用 http://127.0.0.1:8000/docs 操作 API。

1. 创建 Seller Account：
   `POST /api/settings/seller-accounts`

2. 创建 Marketplace：
   `POST /api/settings/marketplaces`

3. 上传并预览报表：
   `POST /api/imports/preview`

4. 确认导入报表：
   `POST /api/imports/confirm`

5. 查看可同步的 SP-API 报表类型：
   `GET /api/spapi/report-types`

6. 创建 SP-API 同步任务：
   `POST /api/spapi/sync-jobs`

7. 运行并刷新同步任务：
   `POST /api/spapi/sync-jobs/{sync_job_id}/run`
   `POST /api/spapi/sync-jobs/{sync_job_id}/refresh`

8. 生成报告：
   `POST /api/reports/generate`

9. 查看报告列表：
   `GET /api/reports`

10. 下载报告：
   `GET /api/reports/{report_id}/excel`

页面流程：

```text
Settings -> 创建店铺 -> 保存 SP-API 自授权 -> 创建市场
-> SP-API Sync -> 创建/运行同步任务 -> 刷新状态
-> Report Center -> 生成报告 -> 下载 Excel
```

## 支持的导入文件

测试样例在：

- `backend/tests/fixtures/business_report.csv`
- `backend/tests/fixtures/inventory_report.csv`
- `backend/tests/fixtures/ads_search_term_report.csv`

Business Report 必需列：

- `Date`
- `Sessions`
- `Units Ordered`
- `Ordered Product Sales`

Inventory Report 必需列：

- `sku`
- `asin`
- `quantity`
- `status`

Ads Search Term Report 必需列：

- `Date`
- `Campaign Name`
- `Search Term`
- `Clicks`
- `Spend`

Orders Report（SP-API TSV）必需列：

- `purchase-date`
- `sku`
- `quantity`
- `currency`
- `item-price`
- `order-status`
- `amazon-order-id`

## LLM 配置

`backend\.env` 可配置：

```env
LLM_PROVIDER=mock
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

国内多数 OpenAI-compatible 厂商可以通过替换 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 接入。没有 API Key 时，系统会跳过 LLM 分析，报告仍可生成。

## Amazon SP-API 自授权与同步

系统使用内部自授权流程，不做 SaaS，不做外部卖家点击授权。Amazon 后台生成的 refresh token 会加密保存。V5 使用该 refresh token 换取 LWA access token，并手动触发 Reports API 同步。

当前已开放：

```text
business_sales_traffic -> GET_SALES_AND_TRAFFIC_REPORT
orders_by_date         -> GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL
```

API 可用性说明（已实测）：

- 该账号未注册品牌（Brand Registry），`GET_SALES_AND_TRAFFIC_REPORT`（品牌分析类）对其永久返回 403，因此销售流量报表不可用。
- 全部订单报表 `GET_FLAT_FILE_ALL_ORDERS_DATA_BY_ORDER_DATE_GENERAL` 已验证可用（TSV 输出），作为 Phase 1 主数据源，用于订单销售趋势分析。
- 订单报表可能含买家地址等 PII 列。当前内部版本保留 raw 原始文件和 `RawReportRow` 便于重算、排错、对账；标准化层、报告、Excel、LLM snapshot 只使用 SKU/数量/金额/币种/订单状态等非买家维度字段。

Raw 数据边界：

- `backend/storage/raw` 保存 Amazon 返回的原始文件，`raw_report_rows.row_json` 保存解析后的原始行。
- UI/API/Excel/LLM 不返回、不读取 Orders raw PII 字段，只读取 `NormalizedOrderDaily` 聚合后的日/SKU/币种数据。
- 当前定位是内部自用、只连自己的店铺、不做 SaaS；因此 raw 层保留原始文件是对账和审计取舍，不作为当前版本阻塞项。
- 如果未来公开部署、多租户或过隐私审查，应增加 `ORDERS_RAW_MODE=keep|redact`、`RAW_RETENTION_DAYS`、raw storage 加密、访问控制和定期清理。

Listing、库存、财务、FBA 报表仍处于 disabled 状态，等对应 parser 和清洗规则明确后再开放。

在 `backend\.env` 追加：

```env
AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_LWA_TIMEOUT_SECONDS=15
TOKEN_ENCRYPTION_KEY=
```

生成 Fernet 加密 key：

```powershell
cd backend
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

在 Amazon 后台点击“授权应用”生成 refresh token，然后在 Settings 页面保存授权，或使用接口保存：

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/auth/amazon/self-authorizations `
  -ContentType "application/json" `
  -Body '{"selling_partner_id":"A3FHEXAMPLEYWS","refresh_token":"Atzr|example","token_type":"bearer"}'
```

本地检查配置是否完整：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/auth/amazon/status
```

查看已保存授权：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/auth/amazon/authorizations
```

查看 V5 已开放的 SP-API 报表类型：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/spapi/report-types
```

接口不会返回 refresh token 明文，也不会返回加密后的 refresh token。不要使用真实 token 写入 README、Git、聊天或截图。真实 token 泄露后，应在 Amazon 后台重新生成并撤销旧授权。

V5 已知边界：

- 已完成：内部 refresh token 录入、Fernet 加密保存、授权列表安全返回、授权删除。
- 已完成：手动 SP-API 同步任务、Reports API 创建/轮询/下载、Sales and Traffic 报表入库。
- 已完成：全部订单报表（Orders）TSV 入库、订单销售趋势（日/周/月）和 SKU 表现分析、多币种分列。
- 已完成：LLM Prompt 版本化、结构化输出校验、AI Insights Excel 输出。
- 未完成：自动定时同步、后台队列、Ads API、Orders raw 脱敏/保留期策略、Amazon 写操作。
- 未完成：退款净额、广告归因、汇率换算、库存/财务报表。
- 未完成：生产登录系统、密钥轮换、Amazon 侧授权撤销检测。

## 目录结构

```text
backend/
  app/
    api/routes/          API 路由
    core/                配置、数据库、存储
    domain/              枚举
    models/              SQLAlchemy 模型
    schemas/             Pydantic schema
    services/            导入、标准化、报告、LLM、设置、Amazon 自授权、安全服务
    web/                 服务端页面模板和 CSS
  migrations/            Alembic 迁移
  tests/                 自动化测试和样例文件
docs/
  superpowers/specs/     架构/需求设计
  superpowers/plans/     实施计划
```

## 数据和文件存储

- 数据库默认使用本地 Docker Postgres：`postgresql+psycopg://copilot:copilot@localhost:5432/copilot`
- 后端从 `backend` 目录启动，`STORAGE_ROOT=storage` 时原始文件和报告文件会保存到：`backend/storage`
- `backend/storage` 已在 `.gitignore` 中，不会提交到 Git。

## 回滚

当前 V2 完成点已打 tag：

```powershell
git checkout v2-operations-complete
```

查看历史：

```powershell
git log --oneline --decorate
```

回到某个提交：

```powershell
git checkout <commit_sha>
```

