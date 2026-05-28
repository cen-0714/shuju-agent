# Amazon Daily Copilot

内部使用的 Amazon 多店铺日常运营数据分析工具。当前版本面向手动导出文件导入、数据落库、报告生成，以及 Amazon SP-API 授权接入前的业务闭环验证。

## 当前功能

- 店铺配置：维护 `Seller Account + Marketplace`，支持美洲站基础市场信息。
- 手动导入：支持 Business Report、Inventory Report、Ads Search Term Report 的 CSV/XLSX 预览与确认导入。
- 数据持久化：保存原始文件、原始行、标准化后的业务/库存/广告搜索词数据。
- 导入删除：删除导入会移除原始文件和相关明细数据，并把受影响报告标记为 `stale`。
- 报告生成：支持单店铺/全部店铺、单日/日期范围报告。
- 报告下载：支持 Markdown 查看和 Excel 下载。
- LLM 分析：支持 OpenAI-compatible 接口；没有 API Key 时自动跳过，不影响报告生成。
- Amazon SP-API 授权：提供 Website OAuth Login URI / Redirect URI，支持保存加密 refresh token，供后续 API 拉取版本使用。
- 页面入口：Dashboard、Data Import、Report Center、Settings 四个服务端页面。

暂未实现：Amazon SP-API 自动拉取数据、Ads API 自动拉取、SP-API 签名请求、限流轮询、登录权限、异步任务队列、推送通知。

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
STORAGE_ROOT=backend/storage
LLM_PROVIDER=mock
"@ | Set-Content -Encoding UTF8 .env

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
- Amazon OAuth 配置状态：http://127.0.0.1:8000/api/auth/amazon/status

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

5. 生成报告：
   `POST /api/reports/generate`

6. 查看报告列表：
   `GET /api/reports`

7. 下载报告：
   `GET /api/reports/{report_id}/excel`

页面 `/imports`、`/reports`、`/settings` 已提供基础入口和控件；后续版本可以继续补前端交互，把页面操作完整串起来。

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

## LLM 配置

`.env` 可配置：

```env
LLM_PROVIDER=mock
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=
LLM_MODEL=gpt-4.1-mini
LLM_TIMEOUT_SECONDS=30
```

国内多数 OpenAI-compatible 厂商可以通过替换 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 接入。没有 API Key 时，系统会跳过 LLM 分析，报告仍可生成。

## Amazon SP-API OAuth 配置

V3 只实现授权回调和 refresh token 加密保存，不会自动拉取订单、库存、报表或广告数据。

在 `.env` 追加：

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

本地检查配置是否完整：

```powershell
curl http://127.0.0.1:8000/api/auth/amazon/status
```

授权成功后查看已保存授权：

```powershell
curl http://127.0.0.1:8000/api/auth/amazon/authorizations
```

接口不会返回 refresh token 明文，也不会返回加密后的 refresh token。

公网反向代理建议只放行：

- `/api/auth/amazon/login`
- `/api/auth/amazon/callback`
- `/api/auth/amazon/status`
- `/api/health`

不建议公网暴露后台页面、导入接口、报告接口、设置接口或 `/docs`。

V3 已知边界：

- 已完成：Amazon OAuth state 校验、LWA authorization code 换 token、refresh token 加密保存。
- 已完成：已使用/过期/不匹配的 state 会在换 token 和读取敏感配置前被拒绝。
- 未完成：SP-API 签名请求、Reports API 拉取、Orders API 拉取、Inventory API 拉取、Ads API 授权。
- 未完成：生产登录系统、密钥轮换、授权撤销检测、自动同步任务。

## 目录结构

```text
backend/
  app/
    api/routes/          API 路由
    core/                配置、数据库、存储
    domain/              枚举
    models/              SQLAlchemy 模型
    schemas/             Pydantic schema
    services/            导入、标准化、报告、LLM、设置、Amazon OAuth、安全服务
    web/                 服务端页面模板和 CSS
  migrations/            Alembic 迁移
  tests/                 自动化测试和样例文件
docs/
  superpowers/specs/     架构/需求设计
  superpowers/plans/     实施计划
```

## 数据和文件存储

- 数据库默认使用本地 Docker Postgres：`postgresql+psycopg://copilot:copilot@localhost:5432/copilot`
- 原始文件和报告文件默认保存到：`backend/storage`
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

