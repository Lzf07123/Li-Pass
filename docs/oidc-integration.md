# OIDC 对接指南

Portal OSS 是一个符合 OIDC/OAuth2 授权码流程的身份提供商（IdP）。授权网站按本文档接入后，用户即可“注册一次、登录所有已授权网站”。

## 1. 标准端点

假设门户 issuer 为 `https://auth.example.com`（本地示例为 `http://localhost:8000`）：

| 端点 | 说明 |
| --- | --- |
| `GET /.well-known/openid-configuration` | 发现文档（推荐从这里读取所有端点） |
| `GET /oauth2/authorize` | 发起授权（授权码 + PKCE S256） |
| `POST /oauth2/token` | 用授权码换令牌 |
| `GET /oauth2/userinfo` | 获取用户信息（Bearer 令牌） |
| `GET /oauth2/jwks` | 令牌签名公钥 |

支持范围：`openid`、`profile`、`email`；仅支持 `response_type=code` 与 PKCE `S256`。

## 2. 授权码 + PKCE 流程（公开客户端）

### 2.1 生成 PKCE

```python
import base64
import hashlib
import secrets

verifier = secrets.token_urlsafe(48)
challenge = base64.urlsafe_b64encode(
    hashlib.sha256(verifier.encode()).digest()
).rstrip(b"=").decode()
```

### 2.2 跳转授权页

```text
GET {issuer}/oauth2/authorize?response_type=code
    &client_id=YOUR_CLIENT_ID
    &redirect_uri=https%3A%2F%2Fyour-site.example%2Fcallback
    &scope=openid%20profile%20email
    &state=RANDOM_STATE
    &nonce=RANDOM_NONCE
    &code_challenge=CHALLENGE
    &code_challenge_method=S256
```

用户登录并同意授权后，门户跳回：

```text
https://your-site.example/callback?code=AUTHORIZATION_CODE&state=RANDOM_STATE
```

必须校验 `state` 与发起时一致。用户拒绝或被封禁时跳回：

```text
https://your-site.example/callback?error=access_denied&state=RANDOM_STATE
```

被网站封禁时额外带 `error_description=account_blocked`。

### 2.3 换令牌

公开客户端：

```bash
curl -X POST {issuer}/oauth2/token \
  -d grant_type=authorization_code \
  -d code=AUTHORIZATION_CODE \
  -d redirect_uri=https://your-site.example/callback \
  -d client_id=YOUR_CLIENT_ID \
  -d code_verifier=VERIFIER
```

机密客户端（有 `client_secret`）额外传 `client_secret=...`。

成功响应：

```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 900,
  "id_token": "..."
}
```

### 2.4 获取用户信息

```bash
curl {issuer}/oauth2/userinfo -H "Authorization: Bearer ACCESS_TOKEN"
```

```json
{
  "sub": "uuid",
  "email": "user@example.com",
  "email_verified": true,
  "nickname": "Alice",
  "name": "Alice"
}
```

## 3. 示例代码

### Python（requests）

完整实现见仓库 `examples/demo-site/app.py`。核心：

```python
import requests

# 1. 跳转 authorize（见 2.2），回调拿到 code 后：
token = requests.post(
    f"{issuer}/oauth2/token",
    data={
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": verifier,
    },
    timeout=10,
).json()

user = requests.get(
    f"{issuer}/oauth2/userinfo",
    headers={"Authorization": f"Bearer {token['access_token']}"},
    timeout=10,
).json()
```

### Node.js（fetch）

```js
const params = new URLSearchParams({
  grant_type: "authorization_code",
  code,
  redirect_uri,
  client_id,
  code_verifier: verifier,
});
const token = await fetch(`${issuer}/oauth2/token`, {
  method: "POST",
  headers: { "Content-Type": "application/x-www-form-urlencoded" },
  body: params,
}).then((r) => r.json());

const user = await fetch(`${issuer}/oauth2/userinfo`, {
  headers: { Authorization: `Bearer ${token.access_token}` },
}).then((r) => r.json());
```

## 4. 注册客户端

管理员登录门户后在 **授权网站管理**（`/admin/clients`）创建应用，填写：

- 名称、首页地址（应用广场“进入”链接）、回调地址（每行一个）
- 公开客户端（仅 PKCE）或机密客户端（生成 `client_secret`，只显示一次）

也可用管理 API：`POST /api/v1/admin/clients`。

## 5. 网站自助黑名单

机密客户端可用 HTTP Basic（`client_id:client_secret`）管理自己的黑名单：

```bash
# 封禁
curl -u CLIENT_ID:CLIENT_SECRET -X POST {issuer}/oauth2/client/blocks \
  -H "Content-Type: application/json" \
  -d '{"email":"bad@example.com","reason":"滥用"}'

# 列表
curl -u CLIENT_ID:CLIENT_SECRET {issuer}/oauth2/client/blocks

# 解封
curl -u CLIENT_ID:CLIENT_SECRET -X DELETE \
  {issuer}/oauth2/client/blocks/BLOCK_ID
```

被封禁账号：授权时返回 `error=access_denied&error_description=account_blocked`；换令牌与 userinfo 返回 403；解封后立即恢复。

## 6. 常见错误

| 错误 | 含义 |
| --- | --- |
| `invalid_request` | 参数缺失/非法（如缺少 PKCE） |
| `invalid_scope` | scope 不在客户端允许范围或缺少 `openid` |
| `unauthorized_client` | 客户端不存在/停用 |
| `invalid_redirect_uri` | 回调地址不在白名单 |
| `access_denied` | 用户拒绝或账号被该网站封禁 |
| `invalid_grant` | 授权码无效/过期/已使用或 PKCE 校验失败 |
| `invalid_client` | client_id/secret 错误 |
| `invalid_token` | access token 无效或过期 |

## 7. acr 声明

`id_token` 携带 `acr`：

- `urn:portal-oss:acr:1fa`：仅密码登录
- `urn:portal-oss:acr:2fa`：经过邮箱验证码 / TOTP / 恢复码二次验证

需要强认证的网站可校验该声明，拒绝 1fa 会话。

## 8. 安全要求

- 必须校验 `state` 与 `nonce`。
- 公开客户端必须使用 PKCE；机密客户端在服务端保管 secret。
- `redirect_uri` 必须精确匹配门户白名单。
- 授权码只能使用一次，10 分钟有效。
