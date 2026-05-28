# Amazon Daily Copilot V3 SP-API OAuth 授权设计

## 目标

V3 的目标是让系统具备 Amazon SP-API Website OAuth 授权能力：提供公网可访问的 Login URI 和 Redirect URI，接收 Amazon 回调，校验 state，用 `spapi_oauth_code` 向 Login With Amazon 换取 refresh token，并把授权结果安全保存到数据库。

V3 只解决“能被 Amazon 回调并保存授权凭证”这一层，不在本版本拉取订单、库存、报表或广告数据。

## 官方流程依据

Amazon SP-API 授权流程中，Amazon 会请求应用的登录入口，并带上：

```text
amazon_callback_uri
amazon_state
selling_partner_id
```

应用需要创建自己的 `state`，再把用户重定向回 `amazon_callback_uri`。

Amazon 最终会请求应用注册的 Redirect URI，并带上：

```text
state
selling_partner_id
spapi_oauth_code
```

`spapi_oauth_code` 是 LWA authorization code，需要换取 refresh token。

参考：

- https://developer-docs.amazon.com/sp-api/docs/selling-partner-appstore-authorization-workflow?ld=ASXXSPAPIDirect
- https://developer-docs.amazon.com/sp-api/lang-es_ES/docs/website-authorization-workflow
- https://developer-docs.amazon.com/sp-api/lang-US/docs/authorize-public-applications

## V3 包含

- 新增 Amazon OAuth Login URI：
  ```text
  GET /api/auth/amazon/login
  ```

- 新增 Amazon OAuth Redirect URI：
  ```text
  GET /api/auth/amazon/callback
  ```

- 新增授权状态查询接口：
  ```text
  GET /api/auth/amazon/status
  GET /api/auth/amazon/authorizations
  ```

- 新增 OAuth state 会话表。
- 新增 Amazon 授权记录表。
- 新增 LWA token exchange service。
- 新增 refresh token 加密存储。
- 新增 Amazon OAuth 配置项。
- 新增部署说明：公网只暴露 `/api/auth/amazon/*` 和 `/api/health`。
- 新增测试覆盖：state 校验、过期、重复使用、token exchange 成功和失败。

## V3 明确不做

- 不调用 SP-API Reports API。
- 不调用 SP-API Orders API。
- 不调用 SP-API Inventory API。
- 不调用 Amazon Ads API。
- 不做自动同步任务。
- 不做 API 限流、重试和报表轮询。
- 不把授权自动绑定到某个 Marketplace。
- 不做完整登录系统。
- 不把后台页面开放到公网。
- 不处理买家 PII 数据。
- 不自动修改 Listing、价格、广告、bid、预算、targeting 或否词。

这些内容必须进入后续版本，不能在 V3 中隐式实现。

## 后续 Backlog

V4 需要继续做：

- SP-API client 签名和 AWS IAM role 配置。
- 用 refresh token 换 access token。
- Reports API 创建报表、轮询状态、下载文件。
- 把 API 下载文件送入现有 RawDataset -> RawRows -> NormalizedRows 流水线。
- 处理 401、403、429、5xx。
- 针对不同 marketplace 配置 SP-API endpoint。
- Amazon Ads API OAuth 和 profile 绑定。

上线前还需要做：

- 后台登录和访问控制。
- 生产数据库备份。
- token 密钥轮换策略。
- HTTPS 和反向代理安全规则。
- 审计日志完善。

## 配置项

`.env` 增加：

```env
PUBLIC_BASE_URL=https://spapi.yourdomain.com

AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token

AMAZON_OAUTH_LOGIN_PATH=/api/auth/amazon/login
AMAZON_OAUTH_REDIRECT_PATH=/api/auth/amazon/callback
AMAZON_OAUTH_STATE_TTL_MINUTES=10

TOKEN_ENCRYPTION_KEY=
```

规则：

- `PUBLIC_BASE_URL + AMAZON_OAUTH_REDIRECT_PATH` 必须和 Amazon Developer Console 中配置的 Redirect URI 完全一致。
- `TOKEN_ENCRYPTION_KEY` 必须存在，否则 callback 不允许保存 refresh token。
- `AMAZON_LWA_CLIENT_SECRET` 和 `TOKEN_ENCRYPTION_KEY` 不得提交到 Git。
- `AMAZON_LWA_TOKEN_URL` 默认使用 `https://api.amazon.com/auth/o2/token`。

## 数据模型

### AmazonAuthorizationSession

用途：保存一次 OAuth 授权流程的 state 和 Amazon 初始参数。

字段：

```text
id
state
amazon_state
amazon_callback_uri
selling_partner_id
status
expires_at
consumed_at
error_message
created_at
updated_at
```

状态：

```text
created
consumed
expired
failed
```

规则：

- `state` 必须随机生成。
- `state` 有唯一约束。
- `state` 只能使用一次。
- 超过 `expires_at` 的 state 不能继续使用。
- `amazon_state` 必须原样带回 Amazon callback URI。

### AmazonAuthorization

用途：保存某个 Amazon seller 的授权结果。

字段：

```text
id
selling_partner_id
seller_account_id
lwa_client_id
refresh_token_encrypted
token_type
authorized_at
status
last_error
created_at
updated_at
```

状态：

```text
active
failed
revoked
```

规则：

- `selling_partner_id` 唯一。
- 初次授权时可以不绑定 `seller_account_id`。
- 如果系统里已有相同 `amazon_seller_id` 的 SellerAccount，可以自动填入 `seller_account_id`。
- 如果找不到 SellerAccount，授权仍保存为 active，但页面/接口必须显示“未绑定内部店铺”。
- refresh token 只保存加密值，不提供 API 返回明文。

## API 设计

### GET /api/auth/amazon/login

请求参数：

```text
amazon_callback_uri
amazon_state
selling_partner_id
```

行为：

1. 校验三个参数存在。
2. 生成本系统 `state`。
3. 创建 `AmazonAuthorizationSession(status=created)`。
4. 构造重定向地址：
   ```text
   amazon_callback_uri?state=<local_state>&amazon_state=<amazon_state>
   ```
5. 返回 307 Redirect。

错误：

- 缺少参数返回 422。
- `amazon_callback_uri` 非 HTTPS 返回 400。
- 写入数据库失败返回 500。

### GET /api/auth/amazon/callback

请求参数：

```text
state
selling_partner_id
spapi_oauth_code
```

行为：

1. 校验参数存在。
2. 查找 `AmazonAuthorizationSession`。
3. 校验未过期、未使用、selling partner 匹配。
4. 校验 LWA 配置和 token encryption key 已配置。
5. 调用 LWA token endpoint。
6. 解析 refresh token。
7. 加密 refresh token。
8. upsert `AmazonAuthorization`。
9. 标记 session 为 consumed。
10. 返回授权成功页面或 JSON。

错误：

- state 不存在返回 400。
- state 已过期返回 400。
- state 已使用返回 400。
- selling partner 不匹配返回 400。
- LWA 配置缺失返回 500。
- LWA token exchange 失败返回 502，并记录 session failed。

### GET /api/auth/amazon/status

返回当前 OAuth 配置状态，不返回 secret：

```json
{
  "public_base_url_configured": true,
  "lwa_client_id_configured": true,
  "lwa_client_secret_configured": true,
  "token_encryption_key_configured": true,
  "login_uri": "https://spapi.yourdomain.com/api/auth/amazon/login",
  "redirect_uri": "https://spapi.yourdomain.com/api/auth/amazon/callback"
}
```

### GET /api/auth/amazon/authorizations

返回授权列表，不返回 refresh token：

```json
[
  {
    "id": 1,
    "selling_partner_id": "A3FHEXAMPLEYWS",
    "seller_account_id": 1,
    "status": "active",
    "authorized_at": "2026-05-28T00:00:00Z"
  }
]
```

## Token Exchange 设计

新增服务：

```text
backend/app/services/amazon/lwa.py
```

职责：

- 向 LWA token endpoint 发送 `POST`。
- 使用 `grant_type=authorization_code`。
- 发送 `code=spapi_oauth_code`。
- 发送 `client_id` 和 `client_secret`。
- 发送 `redirect_uri`，且必须和配置中的公网 Redirect URI 一致。
- 控制 timeout。
- 失败时返回明确错误，不抛出未处理异常到 API 层。

服务返回：

```text
refresh_token
access_token
token_type
expires_in
```

V3 只保存 refresh token。access token 不落库。

## Token 加密设计

新增服务：

```text
backend/app/services/security/tokens.py
```

职责：

- 使用 `TOKEN_ENCRYPTION_KEY` 加密 refresh token。
- 解密能力只给后续 SP-API client 使用。
- 测试使用固定测试 key。

实现选择：

- 使用 `cryptography.fernet.Fernet`。
- `TOKEN_ENCRYPTION_KEY` 使用 Fernet 兼容 key。
- 如果 key 缺失或非法，callback 返回明确错误。

需要新增依赖：

```text
cryptography>=43.0.0
```

## Seller 绑定规则

V3 不强制用户先创建 SellerAccount。

规则：

1. callback 收到 `selling_partner_id`。
2. 查询 `SellerAccount.amazon_seller_id == selling_partner_id`。
3. 找到则绑定 `seller_account_id`。
4. 找不到则保存授权但 `seller_account_id=None`。
5. 后续 Settings 页面可以增加手动绑定功能，但不在 V3 实现。

这样可以避免授权回调因为内部店铺还没建好而失败。

## 公网部署边界

推荐公网域名：

```text
https://spapi.yourdomain.com
```

推荐反向代理只放行：

```text
/api/auth/amazon/login
/api/auth/amazon/callback
/api/auth/amazon/status
/api/health
```

不建议公网开放：

```text
/
/imports
/reports
/settings
/docs
/api/imports/*
/api/reports/*
/api/settings/*
```

如果必须临时开放 `/docs` 调试，调试完成后关闭。

## 错误处理

错误必须结构化返回：

```json
{
  "detail": "state expired"
}
```

内部记录：

- session status
- error message
- last_error

日志规则：

- 可以记录 selling_partner_id。
- 可以记录 session id。
- 不记录 `spapi_oauth_code`。
- 不记录 refresh token。
- 不记录 client secret。

## 验收标准

V3 完成时必须满足：

- `GET /api/auth/amazon/status` 返回 login_uri 和 redirect_uri。
- `GET /api/auth/amazon/login` 能创建 session 并 307 跳转到 Amazon callback URI。
- callback 能校验 state。
- callback 拒绝过期 state。
- callback 拒绝重复使用 state。
- callback 拒绝 selling_partner_id 不匹配。
- callback 能通过 mocked LWA token endpoint 保存加密 refresh token。
- 授权列表不返回 refresh token 明文。
- 未配置 LWA secret 或 token key 时返回明确错误。
- Alembic migration 在 SQLite 和 PostgreSQL 上通过。
- `python -m ruff check .` 通过。
- `python -m pytest -q` 通过。

## 当前没有做但必须记住

- 没有真实拉取 Amazon 报表。
- 没有真实拉取库存、订单、广告。
- 没有处理 SP-API request signing。
- 没有处理 AWS IAM role assume role。
- 没有处理 rate limit。
- 没有把授权绑定到 marketplace。
- 没有做授权失效检测。
- 没有做 refresh token 轮换。
- 没有公网 Nginx/Caddy 配置文件。
- 没有登录系统。

这些是 V4/V5 的范围，不应该混入 V3。

## 自查

- V3 聚焦 OAuth，不扩大到数据同步。
- Login URI 和 Redirect URI 分开设计。
- state 具备随机、过期、一次性使用规则。
- token 使用加密保存。
- 授权和内部店铺绑定允许延后。
- 公网暴露范围默认最小。
- 没有把 Amazon secret 或 token 写入源码。
