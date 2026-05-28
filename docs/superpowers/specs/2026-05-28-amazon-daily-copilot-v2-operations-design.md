# Amazon Daily Copilot V2 运营可用版设计

## 目标

V2 的目标是把 V1 的可验证 MVP 扩展成内部运营可以日常使用的完整日报闭环。

核心流程：

```text
店铺配置
-> 选择店铺
-> 上传报表
-> 预览校验
-> 确认导入落库
-> 保存原始文件
-> 标准化数据
-> 计算指标
-> 生成单日或日期范围报告
-> 可选 LLM 摘要
-> 页面查看
-> Excel 下载
```

V2 仍然是内部工具，不做外部 SaaS。V2 不接 Amazon SP-API 或 Amazon Ads API，先把手动导入到日报生成的业务闭环跑稳。

## V1 基线

V1 已完成：

- FastAPI 后端服务。
- SQLAlchemy ORM 模型。
- Alembic 数据库迁移。
- PostgreSQL 本地 Docker 环境。
- 手动上传报表预览 API。
- Business Report、Inventory Report、Ads Search Term Report 的 schema 识别。
- 报表字段校验。
- 标准化服务。
- 指标计算服务。
- Markdown 和 Excel 报告生成服务。
- Mock LLM provider 和 LLM 输出安全校验。
- Dashboard、Data Import、Report Center、Settings 四个基础页面。
- Amazon API readiness 文档。

V1 还没有完成真实运营闭环：

- 店铺配置还不能在页面维护。
- 导入只做到 preview，没有确认导入落库。
- 原始文件保存、raw rows、normalized rows 和 metrics 没有形成可追溯闭环。
- Report Center 还不能由用户选择店铺和日期后生成报告。
- 删除导入后不能标记受影响报告为 stale。
- 真实 LLM provider 尚未接入。

## V2 范围

### V2 包含

- 基础店铺配置页面。
- 店铺粒度为 `Seller Account + Marketplace`。
- 报告和导入页面必须选择店铺，支持单店铺和全部店铺。
- 支持单日报告和日期范围报告。
- 支持 Business Report、Inventory Report、Ads Search Term Report 的确认导入。
- 保存上传原始文件。
- 保存 raw dataset 和 raw rows。
- 保存标准化数据。
- 计算并保存或重算相关 metrics。
- 报告同步生成。
- 报告中心查看 Markdown。
- 报告中心下载 Excel。
- 删除导入记录。
- 删除导入后标记相关报告为 `stale`。
- OpenAI-compatible LLM 可选接入。
- LLM 失败不阻塞报告生成。
- Dashboard 展示最近报告、stale 报告、最近导入和失败提醒。

### V2 不包含

- Amazon SP-API 真实接入。
- Amazon Ads API 真实接入。
- 异步任务队列。
- 登录、用户权限和角色系统。
- 自动发送邮件、飞书、钉钉或企业微信。
- 自动修改 Listing、价格、广告 bid、预算、targeting 或否词。
- 复杂 BI 看板。
- 周期趋势预测。
- 买家 PII 导入和分析。

## 实现路线

V2 采用纵向切片闭环。

第一条闭环优先跑通 Business Report：

```text
配置店铺
-> 选择店铺
-> 上传 Business Report
-> 预览
-> 确认导入
-> 标准化
-> 生成报告
-> 下载 Excel
```

Business Report 跑通后，再把 Inventory Report 和 Ads Search Term Report 接进同一套导入和报告流水线。

这样可以保证每个阶段都有可运行结果，不会只做底层模型但页面不可用。

## 店铺模型

V2 的“店铺”不是单独新建一个独立实体，而是页面层的组合视图：

```text
Store Option = SellerAccount + Marketplace
```

示例：

```text
店铺A - US
店铺A - CA
店铺B - US
店铺B - MX
```

原因：

- Amazon 实际运营通常按 Seller 和 Marketplace 组合看数据。
- 后续扩展欧洲、日本或其他区域时不用重做模型。
- API 接入后也能自然映射到 seller account、marketplace id 和 ads profile。

Settings 页面维护：

- Seller Account。
- Marketplace。
- 是否启用。

导入页和报告页使用 `store-options` 接口获取可选店铺。

## 页面设计

V2 保持 4 个主页面。

### Dashboard

展示：

- 最近生成的有效报告。
- stale 报告提醒。
- 最近导入任务。
- 启用店铺数量。
- 最近失败导入。

Dashboard 不做复杂 BI，优先做运营入口和状态提醒。

### Data Import

页面流程：

```text
选择店铺
选择报表类型
选择日期或日期范围
上传文件
点击预览
查看校验结果
确认导入
查看导入历史
删除导入
```

规则：

- 必须选择店铺后才能预览。
- 必须选择报表类型。
- 必须选择日期或日期范围。
- 预览通过后才能确认导入。
- 确认导入后保存原始文件并写入数据库。
- 删除导入必须影响相关 raw、normalized、metrics 和 reports 状态。

### Report Center

页面流程：

```text
选择报告类型：单日或日期范围
选择店铺范围：全部店铺或单店铺
选择日期或日期范围
点击生成报告
查看 Markdown
下载 Excel
查看 stale 状态
重新生成 stale 报告
```

规则：

- 没有选择店铺范围时，生成和下载按钮禁用。
- `全部店铺` 报告包含综合汇总和各店铺分段。
- 单店铺报告只包含该店铺数据。
- stale 报告可以查看，但必须提示数据已变更。
- stale 报告提供重新生成入口。

### Settings

页面能力：

- 新增 Seller Account。
- 编辑 Seller Account。
- 新增 Marketplace。
- 编辑 Marketplace。
- 启用或停用店铺。
- 配置 OpenAI-compatible LLM。

V2 不做登录，也不做团队成员管理。

## API 设计

### Settings API

```text
GET    /api/settings/seller-accounts
POST   /api/settings/seller-accounts
PATCH  /api/settings/seller-accounts/{id}

GET    /api/settings/marketplaces
POST   /api/settings/marketplaces
PATCH  /api/settings/marketplaces/{id}

GET    /api/settings/store-options
```

`store-options` 返回导入页和报告页需要的可选店铺列表。

### Import API

```text
POST   /api/imports/preview
POST   /api/imports/confirm
GET    /api/imports/jobs
GET    /api/imports/jobs/{id}
DELETE /api/imports/jobs/{id}
```

V1 已有 `preview`。V2 补 `confirm`、列表、详情和删除。

`confirm` 必须完成：

- 保存上传原始文件。
- 创建或更新 ImportJob。
- 创建 RawDataset。
- 保存 raw rows。
- 写入 normalized rows。
- 计算或清理相关 metrics。
- 返回导入结果。

### Reports API

```text
POST /api/reports/generate
GET  /api/reports
GET  /api/reports/{id}
GET  /api/reports/{id}/markdown
GET  /api/reports/{id}/excel
POST /api/reports/{id}/regenerate
```

`generate` 请求必须包含：

- `scope_type`: `all_stores` 或 `single_store`
- `seller_account_id` 和 `marketplace_id`，仅单店铺报告需要
- `report_kind`: `single_day` 或 `date_range`
- `report_start_date`
- `report_end_date`

## 数据模型设计

V2 在 V1 模型基础上扩展，不推翻原有模型。

### ImportJob

状态：

```text
pending
previewed
succeeded
failed
deleted
```

ImportJob 记录：

- seller account。
- marketplace。
- report type。
- date range。
- source。
- status。
- error code。
- error message。
- linked raw dataset。

### RawDataset

RawDataset 保存每次确认导入的文件元数据：

- `seller_account_id`
- `marketplace_id`
- `source`
- `report_type`
- `date_range_start`
- `date_range_end`
- `schema_version`
- `raw_file_path`
- `raw_file_checksum`
- `row_count`
- `data_status`
- `data_version`

raw rows 和 normalized rows 必须能追踪到 `raw_dataset_id`。

### DailyReport

V2 扩展 DailyReport：

- `scope_type`: `single_store` 或 `all_stores`
- `seller_account_id`
- `marketplace_id`
- `report_start_date`
- `report_end_date`
- `report_kind`: `single_day` 或 `date_range`
- `status`: `active`、`stale` 或 `failed`
- `markdown_path`
- `excel_path`
- `llm_status`
- `llm_error`

单店铺报告使用 seller account 和 marketplace。全部店铺报告不绑定单个 seller account 和 marketplace。

## 文件存储设计

V2 增加 `StorageBackend` 抽象：

```text
StorageBackend
  save_upload()
  delete_file()
  exists()
  resolve_path()
```

V2 实现：

```text
LocalStorageBackend
```

目录：

```text
backend/storage/
  raw/
  reports/
    markdown/
    excel/
```

业务服务只能依赖 `StorageBackend`，不能直接依赖本地磁盘路径。后续可以替换成：

- S3StorageBackend。
- OSSStorageBackend。
- NASStorageBackend。

## 删除导入设计

删除导入时执行：

```text
ImportJob -> deleted
Raw file -> delete
Raw rows -> delete
Normalized rows -> delete
Affected metrics -> delete or mark dirty
Affected reports -> stale
AuditLog -> append delete event
```

规则：

- 审计日志不物理删除。
- 删除失败要回写明确错误。
- 已生成报告不直接删除，改为 `stale`。
- stale 报告可以查看，但必须显示数据已变更，需要重新生成。
- stale 报告下载时必须提示数据已变更。

## 报告生成设计

V2 使用同步报告生成。

流程：

```text
校验店铺范围
校验日期范围
查询已导入数据
聚合指标
生成 DailyReport
生成 Markdown 文件
生成 Excel 文件
可选调用 LLM
返回报告结果
```

单日报告：

- `report_kind=single_day`
- `report_start_date=report_end_date`

日期范围报告：

- `report_kind=date_range`
- `report_start_date < report_end_date`
- V2 只做聚合汇总，不做复杂同比、环比和趋势预测。

如果数据量过大或同步生成超时，返回明确错误，提示缩小日期范围。异步队列放后续版本。

## LLM 设计

V2 接入 OpenAI-compatible API。

配置项：

```text
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=...
LLM_MODEL=...
LLM_TIMEOUT_SECONDS=30
```

规则：

- 未配置 API key 时，不调用真实 LLM。
- 配置 API key 时，报告生成后调用 LLM。
- LLM 成功时保存摘要、findings 和证据引用。
- LLM 失败时，报告仍然可以生成成功，设置 `llm_status=failed` 和 `llm_error`。
- LLM 输出必须通过 validator。
- LLM 不能接收原始 CSV，只接收结构化 snapshot。
- LLM 不允许建议自动改价、自动改广告、自动改 listing 或任何自动 Amazon 账号操作。

Provider 名称使用：

```text
openai_compatible
```

这样 OpenAI 官方和兼容 OpenAI 格式的国内模型 API 都可以通过 `base_url` 和 `model` 切换。

## 错误处理

导入错误：

- 不支持文件类型。
- 文件不可读取。
- 表头无法识别。
- 缺少必需列。
- 日期范围不匹配。
- 重复文件。
- 空文件。
- 标准化失败。
- 原始文件保存失败。
- 删除失败。

报告错误：

- 未选择店铺。
- 日期范围无数据。
- 没有可用指标。
- Markdown 生成失败。
- Excel 生成失败。
- LLM 失败。
- 报告已 stale。

错误必须进入 ImportJob 或 DailyReport 状态，并在页面上可见。

## 安全边界

- 不做登录，但默认部署在本机或内部网络。
- 不导入买家姓名、地址、电话、邮箱、消息或支付数据。
- 不把原始文件发送给 LLM。
- 不把 API key 写入 Git。
- `.env` 不提交。
- 删除导入必须写审计日志。
- LLM 输出必须经过安全校验后才能展示。

## 验收标准

V2 完成时必须满足：

- 可以在 Settings 页面新增和编辑 Seller Account。
- 可以在 Settings 页面新增和编辑 Marketplace。
- 可以启用和停用店铺。
- Data Import 页面可以选择店铺、报表类型、日期范围和文件。
- Data Import 页面可以预览报表校验结果。
- 用户可以确认导入。
- 确认导入后原始文件保存到 storage。
- 确认导入后 RawDataset、raw rows 和 normalized rows 写入数据库。
- Import History 可以查看导入记录。
- 可以删除导入记录。
- 删除导入记录后相关报告变为 stale。
- Report Center 可以选择全部店铺或单店铺。
- Report Center 可以生成单日报告。
- Report Center 可以生成日期范围报告。
- Report Center 可以查看 Markdown 报告。
- Report Center 可以下载 Excel 报告。
- stale 报告可见且有明确提示。
- OpenAI-compatible LLM 配置存在时可以生成 AI 摘要。
- LLM 失败不阻塞报告生成。
- LLM 输出安全校验继续生效。
- Dashboard 展示最近报告、最近导入和 stale 提醒。
- `python -m ruff check .` 通过。
- `python -m pytest -v` 通过。
- Docker Postgres 上 Alembic 迁移通过。
- 本地启动后四个页面可访问。

## 后续版本方向

V3 可以做：

- 登录和内部权限。
- 更完整的报告版本管理。
- 周报、月报和趋势对比。
- 更细的 ASIN、SKU、Campaign 和 Search Term 下钻。
- 异步任务队列。
- 报告自动推送。

V4 可以做：

- SP-API 授权和报表同步。
- Amazon Ads API 授权和广告报表同步。
- API 限流、重试和报表状态轮询。
- 用 API adapter 替换或补充手动上传。

V5 可以做：

- 更完整的异常检测。
- 多模型 provider 管理。
- 高级经营建议。
- 更接近 BI 的自助分析。

## 自查

- 没有把 Amazon API 接入混入 V2。
- 没有把登录权限混入 V2。
- 报告支持单日和日期范围，但 V2 不做复杂趋势分析。
- 店铺选择统一为 `SellerAccount + Marketplace`。
- 删除导入会影响报告状态，避免用户误信旧数据。
- LLM 是可选增强，不阻塞核心日报生成。
