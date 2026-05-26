# Amazon 多店铺综合日报 Copilot MVP 设计

## 目标

构建一个内部使用的 Amazon 店铺数据分析 Copilot，服务于公司自有的多个 Amazon Seller 账号。MVP 聚焦美洲站的每日经营报告，同时从数据模型上保留未来扩展到欧洲、日本和其他 Marketplace 的能力。

这个系统不是自动化 Amazon 运营 Agent。系统负责采集数据、标准化报表、计算指标、识别明显异常、生成 LLM 可读取的数据快照、生成日报，并把报告交给运营人员判断。系统不得自动修改 Listing、价格、广告、Bid、预算、否词或任何 Amazon 账号设置。

## 当前约束

- 系统只供内部使用，不做面向外部客户的 SaaS 产品。
- 公司有多个自有 Amazon 店铺。
- 第一阶段生产范围是美洲站。
- 未来区域扩展不能要求重做数据库或报告流水线。
- 目前还没有 SP-API 和 Amazon Ads API 凭证。
- 用户可以登录 Seller Central 和 Amazon Ads Console。
- 用户还没有稳定的手动报表导出流程。
- MVP 必须避免处理买家 PII 和敏感买家级数据。

## 推荐方案

采用 API-ready 的手动导入 MVP。

第一版通过上传 Seller Central 和 Amazon Ads 的报表文件来跑通系统。同时，数据源边界设计为 Adapter 接口，后续 SP-API 和 Amazon Ads API 接入时，必须进入同一套 Raw Dataset 流水线，而不是绕过或替换核心系统。

```text
ManualFileAdapter    -> RawDataset
SPAPIReportAdapter   -> RawDataset
AdsAPIReportAdapter  -> RawDataset

RawDataset -> NormalizedDataset -> Metrics -> DailyReport -> LLM Summary
```

MVP 只实现 `ManualFileAdapter`。`SPAPIReportAdapter` 和 `AdsAPIReportAdapter` 作为未来适配器先定义同一套输出契约。

## 产品范围

### MVP 包含

- 管理多个内部 Seller 账号。
- 管理每个 Seller 账号下的 Marketplace。
- 第一阶段优先支持美洲站 Marketplace。
- 上传每日或近期报表文件。
- 校验报表类型、必需列、Seller 账号、Marketplace 和日期范围。
- 保存原始上传文件和导入元数据。
- 将报表行标准化为内部数据表。
- 计算每日销售、流量、广告和库存指标。
- 生成多店铺综合日报。
- 生成单店铺报告分段。
- 基于计算指标生成结构化 LLM Snapshot。
- 使用 LLM 解释趋势、异常、风险和建议人工处理动作。
- 保存报告版本，并记录数据版本、指标版本、Prompt 版本和模型版本。
- 提供基础内部 Web UI，包括 Dashboard、Data Import、Report Center 和 Settings。

### MVP 不包含

- 外部 SaaS 租户注册。
- 客户计费、外部组织或复杂客户角色。
- 自动修改 Listing。
- 自动改价。
- 自动修改广告 Bid、预算、Targeting 或否词。
- 买家 PII 导入或分析。
- 买家消息、地址、电话、邮箱或支付数据。
- 严格利润口径的财务核算。
- 深度 PPC 优化。
- 完整 BI 自助分析。
- 把爬虫作为核心数据源。

## MVP 报表输入

MVP 支持少量关键报表类别。不同导出格式的列名可能不同，因此导入器必须为每种映射保存 `schema_version`。

### Business Reports

用途：销售与流量表现。

第一版支持：

- 店铺级每日销售与流量。
- 可用时支持 ASIN 或 Child Item 级销售与流量。
- 可用字段包括 Sessions、Page Views、Units Ordered、Ordered Product Sales、Conversion Rate、Buy Box Percentage。

### Inventory Reports

用途：库存可见性和风险识别。

第一版支持：

- Active Listing 库存。
- 可用字段包括 SKU、ASIN、Fulfillment Channel、Available Quantity、Listing Status、Price。
- 简单低库存和非活跃 Listing 标记。

### Ads Reports

用途：广告效率概览。

第一版支持：

- Sponsored Products Campaign、Targeting 或 Search Term 报表。
- 可用字段包括 Spend、Impressions、Clicks、CPC、Sales、Orders、ACOS、ROAS、CTR、CVR。
- 高花费低回报标记和 Search Term 浪费提示。

## 数据模型原则

数据库保留内部多店铺能力，但不做完整 SaaS 复杂度。

核心维度：

- `organization`：一个内部公司组织。
- `seller_account`：每个公司自有 Amazon Seller 账号。
- `marketplace`：区域、Marketplace ID、国家、时区和币种。
- `data_source`：手动上传、SP-API、Ads API 或未来第三方数据源。
- `report_type`：Business Report、Inventory Report、Ads Campaign Report、Ads Targeting Report、Ads Search Term Report。

每个导入数据集必须包含：

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

MVP 使用三层数据：

- Raw Layer：原始文件、解析后的原始行、导入元数据和校验结果。
- Normalized Layer：清洗后的业务行，统一 Seller 账号、Marketplace、日期、币种、ASIN、SKU、Campaign 和 Search Term 字段。
- Metrics Layer：由代码计算出的指标，供 Dashboard、Report 和 LLM Snapshot 使用。

LLM 输出永远不能作为关键指标的事实来源。

## 数据新鲜度

MVP 必须承认 Amazon 数据存在延迟和回填。

支持状态：

- `preliminary`：当天或刚上传的数据，后续可能变化。
- `stable`：T+1 或 T+2 数据，适合日报分析。
- `final`：更早的数据，适合复盘和趋势分析。

当报告使用 `preliminary` 或 `stable` 数据时，必须展示数据新鲜度说明。广告销售额、广告订单、ACOS、ROAS、Search Term、退款和财务指标尤其容易在首次可见后继续变化。

## 导入流程

1. 用户打开 Data Import 页面。
2. 用户选择 Seller 账号、Marketplace、报表类型和日期范围。
3. 用户上传 CSV 或 Excel 文件。
4. 系统将文件保存到对象存储或本地文件存储。
5. 系统计算文件 checksum，并检查是否重复导入。
6. 系统解析表头并识别字段映射 schema。
7. 系统校验必需列。
8. 系统预览行数、检测到的日期、检测到的币种和样例行。
9. 用户确认导入。
10. 系统写入 Raw Import 记录。
11. 系统标准化数据行。
12. 系统计算受影响的指标。
13. 系统将导入任务标记为成功，或写入明确类型的失败原因。

## API-ready Adapter 契约

手动上传和未来 API 必须输出同一个逻辑 Raw Dataset Envelope。

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

未来 API Adapter 不允许直接写入 Normalized 表或 Metrics 表。它们必须先创建 Raw Dataset，然后复用和手动上传相同的标准化与指标计算流水线。

## 指标范围

MVP 聚焦每日经营指标。

销售与流量：

- ordered product sales
- units ordered
- sessions
- page views
- conversion rate
- unit session percentage when present
- buy box percentage when present

广告：

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

库存：

- available quantity
- inactive listing flag
- low-stock flag
- simple days-of-cover when sales velocity is available

派生健康标记：

- 销售额明显下滑
- 流量明显下滑
- 转化率明显下滑
- 广告花费上升但销售没有提升
- 高花费但低订单或零订单
- 低库存
- Listing 非活跃
- 报表数据缺失

指标定义必须包含指标名、公式、来源字段、时间粒度、币种规则和版本。第一版可以作为应用种子配置保存。

## 每日报告

MVP 日报包含：

- 经营摘要。
- 多店铺合计。
- 店铺级销售与广告摘要。
- 正向变化 Top 项。
- 负向变化 Top 项。
- 库存风险段落。
- 广告浪费段落。
- 数据缺失或数据过期提醒。
- LLM 经营解读。
- 建议人工处理动作。
- 数据新鲜度和报告版本元数据。

第一版报告格式：

- JSON：系统内部存档。
- Markdown：Web 页面展示。
- Excel：运营人员下载。

PDF 可以在 Markdown 和 Excel 报告结构稳定后再加入。

## LLM 分析设计

LLM 接收的是紧凑的结构化 Snapshot，不接收原始 CSV 文件或原始 API 响应。

Snapshot 内容：

- 报告元数据
- 包含的 Seller 账号
- 包含的 Marketplace
- 数据新鲜度摘要
- 使用的指标定义
- 聚合指标
- 店铺级指标摘要
- 异常标记
- 选中的 ASIN、Campaign 或 Search Term 高亮信息

LLM 必须输出结构化 JSON，包括：

- summary
- findings
- evidence references
- possible causes
- recommended human actions
- risk level
- confidence
- human review required flag

Output Validator 必须检查：

- JSON Schema 有效。
- 证据引用存在于 Snapshot 中。
- 数值没有被编造。
- 建议不包含自动修改 Amazon 账号的动作。
- 不包含买家 PII。

## Web UI

MVP UI 有四个页面。

### Dashboard

展示最新日报、多店铺合计、店铺状态、数据新鲜度提醒和主要异常。

### Data Import

支持文件上传、报表类型选择、校验预览、导入历史、错误信息和重新导入流程。

### Report Center

展示报告历史、报告状态、报告版本、Markdown 查看、Excel 下载和重新生成动作。

### Settings

支持内部组织配置、Seller 账号、Marketplace、报表类型映射、LLM Provider 配置和推送配置。

## 错误处理

手动导入错误：

- 不支持的文件类型
- 文件不可读取
- 缺少必需列
- 未知 schema
- Seller 账号不匹配
- Marketplace 不匹配
- 日期范围不匹配
- 文件重复
- 数据集重复
- 空数据集
- 标准化失败
- 指标计算失败

未来 API 错误：

- 授权过期
- 权限不足
- 被限流
- Provider 临时故障
- 报表未就绪
- 报表已取消
- 报表已过期
- Schema 变化
- 数据集不完整

错误必须记录在导入任务或未来同步任务上，并展示在 Data Import 或未来 Data Sync 页面中。

## 安全

- 不导入买家姓名、地址、电话、邮箱、消息或支付数据。
- 不把密钥、Token、原始文件或买家级数据发送给 LLM。
- API Key 和 Token 存放在环境变量或 Secret Manager 中。
- 日志中必须脱敏密钥。
- 上传、导入、报告生成和未来 API 凭证变更必须记录审计日志。
- 内部访问第一版可以从简单的管理员/运营人员角色开始。

## 测试策略

MVP 测试必须覆盖：

- CSV 和 Excel 上传解析。
- 每种支持报表类型的表头映射。
- 缺少列校验。
- 重复 checksum 检测。
- Raw Dataset 创建。
- Business、Inventory 和 Ads 样例报表标准化。
- 销售、广告和库存指标计算。
- 数据新鲜度分类。
- 日报 JSON 生成。
- Markdown 报告渲染。
- Excel 报告生成。
- LLM Snapshot 构建。
- LLM 输出 JSON Schema 校验。
- 针对不安全建议的策略校验。

未来 API Adapter 测试必须验证 SP-API 和 Ads API Adapter 会创建与手动上传相同的 `RawDataset` Envelope。

## 阶段交付

### Phase 1：项目地基

创建仓库结构、后端服务、数据库迁移、后台任务模型、内部配置和基础健康检查。

### Phase 2：手动导入流水线

实现 Data Import、原始文件存储、Schema 检测、校验预览、Raw Dataset 创建、标准化和导入历史。

### Phase 3：指标与日报

实现指标定义、指标计算、异常标记、日报生成、Markdown 展示和 Excel 下载。

### Phase 4：LLM Copilot 摘要

实现 Snapshot 构建、Prompt 编排、LLM Provider Adapter、JSON Schema 校验、证据校验和安全建议检查。

### Phase 5：内部交付

完善 Report Center、推送配置，并可选支持飞书或钉钉摘要推送及报告链接。

### Phase 6：API Readiness 与接入

准备 SP-API 和 Ads API 应用设置、Callback URL、凭证存储、目标 Report Type 矩阵、同步任务记录、限流处理和 Adapter 实现。API Adapter 必须进入已有 Raw Dataset 流水线。

## 验收标准

MVP 完成时必须满足：

- 可以配置多个 Seller 账号。
- 每个 Seller 账号至少可以配置一个美洲站 Marketplace。
- 用户可以上传 Business、Inventory 和 Ads 报表文件。
- 导入前会进行校验并展示确认信息。
- 重复文件会被拒绝或以幂等方式处理。
- 原始文件和 Raw Dataset 元数据会被保存。
- 接受导入后会创建标准化数据行。
- 每日指标会从标准化数据中计算出来。
- 可以生成多店铺综合日报。
- 报告包含数据新鲜度提醒。
- 报告可以用 Markdown 查看。
- 报告可以下载为 Excel。
- LLM 摘要基于结构化 Snapshot 生成。
- LLM 输出必须通过 JSON Schema 和策略校验后才能展示。
- 不安全的自动操作建议会被拒绝或标记为无效。
- 数据源 Adapter 契约已文档化，并为未来 SP-API 和 Ads API Adapter 做好准备。
