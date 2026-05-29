# Amazon Daily Copilot V4 自授权 SP-API 设计

## 目标

V4 的目标是把 Amazon 授权方向纠正为“内部自用自授权”：用户在 Amazon Solution Provider Portal / Developer Console 中点击“授权应用”，手动获得 refresh token，然后在本系统内部录入该 refresh token，系统加密保存，供后续 SP-API 调用使用。

本项目不面向外部卖家开放，不做 SaaS，不做外部卖家点击授权。因此 V4 不再保留 Website OAuth callback 兼容路径。

## 当前结论

V3 已经实现了 Website OAuth Login URI / Redirect URI：

```text
GET /api/auth/amazon/login
GET /api/auth/amazon/callback
```

这套流程适合外部卖家授权或 SaaS 场景。当前项目只给自己的 Amazon 店铺内部使用，多店铺也是自有店铺，所以这套路径会造成误导，应在 V4 中删除或下线。

V4 主路径改为：

```text
Amazon 后台自授权生成 refresh token
-> 内部系统录入 refresh token
-> 系统用 TOKEN_ENCRYPTION_KEY 加密保存
-> 后续用 refresh token 换 access token
-> 调 SP-API 拉取报表/库存/订单
```

## V4 包含

- 新增内部自授权录入接口：

  ```text
  POST /api/auth/amazon/self-authorizations
  ```

- 保留授权列表接口：

  ```text
  GET /api/auth/amazon/authorizations
  ```

- 新增授权删除接口：

  ```text
  DELETE /api/auth/amazon/authorizations/{authorization_id}
  ```

- 修改授权配置状态接口：

  ```text
  GET /api/auth/amazon/status
  ```

- 修改 Settings 页面，增加 Amazon 自授权录入区域。
- 加密保存用户录入的 refresh token。
- 不返回 refresh token 明文。
- 不返回加密后的 refresh token。
- 自动按 `selling_partner_id` 绑定已有 `SellerAccount.amazon_seller_id`，找不到则允许保存为未绑定。
- 删除或下线 V3 Website OAuth callback 主路径。
- 更新 README，明确内部自授权流程。

## V4 明确不做

- 不做外部卖家授权。
- 不做 SaaS 授权流程。
- 不做 Amazon Appstore 公共应用发布流程。
- 不保留 Website OAuth Login URI / Redirect URI 作为业务路径。
- 不要求 `PUBLIC_BASE_URL`。
- 不要求 Cloudflare Tunnel 或公网域名。
- 不做 SP-API Reports API 拉取。
- 不做 SP-API Orders API 拉取。
- 不做 SP-API Inventory API 拉取。
- 不做 Amazon Ads API。
- 不做自动同步任务。
- 不做异步队列。
- 不做 token 轮换。
- 不做授权撤销状态主动检测。

这些内容可以进入后续版本，但不能混入 V4。

## 路径调整

### 删除或下线

V4 删除或返回 404：

```text
GET /api/auth/amazon/login
GET /api/auth/amazon/callback
```

相关服务函数也不再作为主代码保留：

```text
create_login_redirect()
handle_authorization_callback()
get_oauth_status() 中的 login_uri / redirect_uri 输出
```

`amazon_authorization_sessions` 表只服务 Website OAuth state 流程，V4 应通过 Alembic migration 删除该表。

### 保留并调整

保留：

```text
GET /api/auth/amazon/status
GET /api/auth/amazon/authorizations
```

`status` 只返回内部自授权需要的配置状态：

```json
{
  "lwa_client_id_configured": true,
  "lwa_client_secret_configured": true,
  "token_encryption_key_configured": true,
  "token_url": "https://api.amazon.com/auth/o2/token"
}
```

### 新增

新增：

```text
POST /api/auth/amazon/self-authorizations
DELETE /api/auth/amazon/authorizations/{authorization_id}
```

## 配置调整

### 保留

V4 保留这些配置：

```env
AMAZON_LWA_CLIENT_ID=
AMAZON_LWA_CLIENT_SECRET=
AMAZON_LWA_TOKEN_URL=https://api.amazon.com/auth/o2/token
AMAZON_LWA_TIMEOUT_SECONDS=15
TOKEN_ENCRYPTION_KEY=
```

### 删除或不再使用

V4 不再使用这些配置：

```env
PUBLIC_BASE_URL=
AMAZON_OAUTH_LOGIN_PATH=
AMAZON_OAUTH_REDIRECT_PATH=
AMAZON_OAUTH_STATE_TTL_MINUTES=
```

如果 `.env` 里已有这些项，程序应忽略它们。README 不再引导用户填写。

## 数据模型

### 保留 `amazon_authorizations`

继续使用 V3 的 `AmazonAuthorization` 表：

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

规则：

- `selling_partner_id` 唯一。
- `refresh_token_encrypted` 只保存加密值。
- `seller_account_id` 可以为空，表示暂未绑定内部店铺。
- 同一个 `selling_partner_id` 再次录入时执行 upsert，覆盖旧 refresh token。
- 删除授权时可以物理删除记录，也可以把 `status` 改为 `revoked`。V4 采用物理删除，便于内部工具直观管理。

### 删除 `amazon_authorization_sessions`

删除表：

```text
amazon_authorization_sessions
```

删除原因：

- 该表只保存 Website OAuth state。
- 内部自授权不需要 state。
- 保留会持续误导后续开发。

## API 设计

### GET /api/auth/amazon/status

返回：

```json
{
  "lwa_client_id_configured": true,
  "lwa_client_secret_configured": true,
  "token_encryption_key_configured": true,
  "token_url": "https://api.amazon.com/auth/o2/token"
}
```

规则：

- 不返回 client secret。
- 不返回 encryption key。
- 不返回 public base URL。
- 不返回 login URI。
- 不返回 redirect URI。

### POST /api/auth/amazon/self-authorizations

请求：

```json
{
  "selling_partner_id": "A3FHEXAMPLEYWS",
  "refresh_token": "Atzr|example",
  "token_type": "bearer"
}
```

行为：

1. 校验 `selling_partner_id` 非空。
2. 校验 `refresh_token` 非空。
3. 校验 `AMAZON_LWA_CLIENT_ID` 已配置。
4. 校验 `TOKEN_ENCRYPTION_KEY` 已配置且可用。
5. 用 `TOKEN_ENCRYPTION_KEY` 加密 refresh token。
6. 查找 `SellerAccount.amazon_seller_id == selling_partner_id`。
7. 找到则绑定 `seller_account_id`。
8. 找不到则保存 `seller_account_id = null`。
9. 对 `selling_partner_id` 执行 upsert。
10. 返回授权元数据，不返回 token。

响应：

```json
{
  "id": 1,
  "selling_partner_id": "A3FHEXAMPLEYWS",
  "seller_account_id": 1,
  "status": "active",
  "authorized_at": "2026-05-29T00:00:00Z"
}
```

错误：

- 缺少 `selling_partner_id`：422。
- 缺少 `refresh_token`：422。
- LWA client id 未配置：500。
- token encryption key 缺失或非法：500。
- 数据库写入失败：500。

### GET /api/auth/amazon/authorizations

返回授权列表：

```json
[
  {
    "id": 1,
    "selling_partner_id": "A3FHEXAMPLEYWS",
    "seller_account_id": 1,
    "status": "active",
    "authorized_at": "2026-05-29T00:00:00Z"
  }
]
```

规则：

- 不返回 refresh token 明文。
- 不返回 `refresh_token_encrypted`。
- 可以返回 `seller_account_id = null`，表示未绑定内部店铺。

### DELETE /api/auth/amazon/authorizations/{authorization_id}

行为：

1. 查找授权记录。
2. 不存在返回 404。
3. 存在则删除。
4. 返回 204。

V4 删除系统内保存的授权记录，不调用 Amazon 撤销 API。用户如果要撤销 Amazon 侧授权，需要在 Amazon 后台撤销。

## 页面设计

在 Settings 页面新增区域：

```text
Amazon 自授权
```

字段：

```text
selling_partner_id
refresh_token
token_type
```

交互：

- 用户从 Amazon 页面复制 refresh token。
- 粘贴到内部页面。
- 点击保存。
- 保存成功后清空 token 输入框。
- 页面只展示授权状态，不展示 token。
- 可删除授权。

页面提示：

- refresh token 是敏感凭证。
- 不要截图、不要提交 Git、不要发聊天。
- 如果泄露，应在 Amazon 后台重新生成并撤销旧授权。

## 安全要求

- refresh token 只在请求体中短暂出现。
- 服务端不打印 refresh token。
- 服务端不返回 refresh token。
- 测试不能使用真实 token。
- README 不出现真实 token 示例。
- `TOKEN_ENCRYPTION_KEY` 不提交 Git。
- `AMAZON_LWA_CLIENT_SECRET` 不提交 Git。
- 删除授权只删除本地记录，不代表 Amazon 侧撤销。

## 测试要求

新增或调整测试：

- `GET /api/auth/amazon/status` 不再返回 login/redirect URI。
- `GET /api/auth/amazon/login` 返回 404。
- `GET /api/auth/amazon/callback` 返回 404。
- `POST /api/auth/amazon/self-authorizations` 能加密保存 refresh token。
- 重复录入同一 `selling_partner_id` 会更新旧记录。
- 已存在 `SellerAccount.amazon_seller_id` 时自动绑定。
- 未找到内部店铺时保存为未绑定。
- 授权列表不返回明文或密文 token。
- 删除授权成功返回 204。
- 删除不存在授权返回 404。
- Alembic migration 能删除 `amazon_authorization_sessions`。
- `python -m pytest -q` 通过。
- `python -m ruff check .` 通过。

## 运行影响评估

删除 `/api/auth/amazon/login` 和 `/api/auth/amazon/callback` 会影响 V3 的 Website OAuth 测试和文档，但不会影响当前内部自用主流程，因为当前真实使用方式是 Amazon 后台自授权生成 refresh token。

需要同步修改：

```text
backend/app/core/config.py
backend/app/api/routes/amazon_auth.py
backend/app/schemas/amazon.py
backend/app/services/amazon/oauth.py
backend/app/models/amazon.py
backend/migrations/versions/*
backend/tests/test_api_amazon_auth.py
backend/tests/test_amazon_oauth_service.py
backend/tests/test_amazon_oauth_models.py
README.md
```

V4 实施后必须跑：

```powershell
cd backend
python -m pytest -q
python -m ruff check .
python -m alembic upgrade head
```

## 验收标准

- README 不再引导配置 Login URI / Redirect URI。
- README 不再要求公网域名或 Cloudflare Tunnel。
- API 中不再存在 `/api/auth/amazon/login` 和 `/api/auth/amazon/callback`。
- 用户可以录入 Amazon 后台生成的 refresh token。
- refresh token 加密保存。
- 授权列表不泄露 token。
- 用户可以删除本地授权。
- 所有测试通过。
- 迁移可从当前数据库升级到 V4。

## 后续版本

V5 可以继续做：

- 用 refresh token 换 access token。
- 实现 SP-API SigV4/AWS IAM role 配置。
- Reports API 创建、轮询、下载。
- 把 SP-API 下载文件送入现有 RawDataset 流水线。
- 处理 401、403、429、5xx。
- 针对不同 marketplace 配置 SP-API endpoint。
- Amazon Ads API 单独授权和 profile 绑定。
