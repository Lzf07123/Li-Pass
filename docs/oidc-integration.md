# OIDC 对接指南

Li&Pass 是一个符合 OIDC/OAuth2 授权码流程的身份提供商（IdP）。授权网站按本文档接入后，用户即可“注册一次、登录所有已授权网站”。

## 1. 标准端点

假设门户 issuer 为 `https://auth.example.com`。本地示例：

- 单域名网关部署（推荐）：`http://localhost`（浏览器与后端同源，经网关 `/oauth2/` 转发）
- 宿主机直连后端开发：`http://localhost:8000`（前端经 `VITE_API_BASE_URL` 直连）

| 端点 | 说明 |
| --- | --- |
| `GET /.well-known/openid-configuration` | 发现文档（推荐从这里读取所有端点） |
| `GET /oauth2/authorize` | 发起授权（授权码 + PKCE S256） |
| `POST /oauth2/token` | 用授权码换令牌 |
| `GET /oauth2/userinfo` | 获取用户信息（Bearer 令牌） |
| `GET /oauth2/jwks` | 令牌签名公钥 |
| `GET /oauth2/end-session` | RP 发起登出（联邦登出入口） |

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

邮箱验证约束：当请求的 `scope` 包含 `email` 且用户尚未验证邮箱时，门户不会停留在授权页，而是直接 302 跳转到验证邮箱页，并携带 `next`（编码后的原授权请求 URL）：

```text
https://auth.example.com/verify-email?email=user%40example.com&next=https%3A%2F%2Fauth.example.com%2Foauth2%2Fauthorize%3Fresponse_type%3Dcode%26...
```

用户完成邮箱验证后会自动回到原授权流程（`state` 与 PKCE 参数经 `next` 保留），随后按常规流程跳回 `redirect_uri`。未验证邮箱的用户仍可登录门户本身，只是不能完成含 `email` scope 的授权；不请求 `email` scope 的授权不受此限制。

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

`access_token` 15 分钟有效，`id_token` 5 分钟有效；当前不提供刷新令牌。

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
  "name": "Alice",
  "picture": "https://auth.example.com/uploads/avatars/00000000-0000-0000-0000-000000000001/a.jpg"
}
```

claims 按授权 scope 裁剪：`email` scope 才返回 `email` / `email_verified`，`profile` scope 才返回 `nickname` / `name` / `picture`。`picture` 为用户头像的绝对 URL（未设置头像时不返回）。

### 2.5 令牌校验（audience 与密钥轮换）

两类令牌的 `aud` 语义不同，接入方校验时注意区分：

| 令牌 | `aud` | 说明 |
| --- | --- | --- |
| `id_token` | 你的 `client_id` | OIDC 标准：必须校验等于自身 client_id |
| `access_token` | `{issuer}/oauth2/userinfo` | 只用于调用 userinfo 端点；不要用 client_id 去校验它 |

`iss` 均为 `https://auth.example.com`，签名算法为 RS256。JWKS（`/oauth2/jwks`）在密钥轮换期间会同时发布多把公钥（每把带唯一 `kid`），应按 token 头部的 `kid` 选对应公钥，而不是缓存单把公钥。

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

- 名称、回调地址（每行一个）、首页地址（应用广场“进入”链接）、登出地址（取消授权时跳转）
- 公开客户端（仅 PKCE）或机密客户端（生成 `client_secret`，只显示一次）

也可用管理 API：`POST /api/v1/admin/clients`。

仓库内置两个运维脚本（已打进后端镜像）：

```bash
docker compose exec backend python -m scripts.seed_demo_client   # 创建 demo-site 公开客户端
docker compose exec backend python -m scripts.make_admin <邮箱>  # 提升管理员
```

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

> 换令牌与 userinfo 命中黑名单时返回的是 HTTP 403 + 中文提示（如“该账号已被此网站限制访问”），不是 OAuth 错误码；授权跳转阶段才使用标准 `access_denied` 错误。

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

## 7. 登出与联邦登出

门户支持三种登出路径，接入方按自身技术栈任选组合：

1. **RP 发起登出（RP-Initiated Logout）**：用户在你的网站点击退出时，先清掉自己的本地会话，再 302 到 IdP 统一退出。
2. **回程登出（Back-Channel Logout）**：用户从门户（或管理员强制下线）退出时，IdP 服务器间 POST `logout_token` 通知你下线。
3. **浏览器串跳漏斗**：未实现回程通道的网站，门户登出时把各网站的 `logout_uri` 串成一条 `?next=` 链，由浏览器依次跳转清会话。

发现文档中的 `end_session_endpoint`、`backchannel_logout_supported: true`、`frontchannel_logout_supported: false` 描述了门户的支持情况。**门户不实现 front-channel iframe 登出**（第三方 Cookie 已被主流浏览器禁用），请勿依赖该机制。

### 7.1 RP 发起登出

管理员在应用配置中填写「登出回跳白名单」（精确匹配，不做前缀匹配）后，网站这样发起：

```text
GET {issuer}/oauth2/end-session
    ?id_token_hint=ID_TOKEN        # 可选：上次登录收到的 id_token
    &client_id=YOUR_CLIENT_ID      # 与 hint 二选一即可
    &post_logout_redirect_uri=https%3A%2F%2Fyour-site.example%2F
    &state=RANDOM_STATE            # 可选：回跳时原样返回
```

门户校验回跳地址后展示「退出登录」确认页。用户确认后：门户会话被吊销、向支持回程的网站分发 `logout_token`，最后 302 回：

```text
https://your-site.example/?state=RANDOM_STATE
```

注意事项：

- `post_logout_redirect_uri` 必须精确命中白名单，否则门户拒绝并跳到门户首页（不会回跳第三方地址）。
- 即便门户当前没有会话（例如已超时），也会直接 302 回跳，而不是报错。
- 校验 `state` 与发起时一致，防止跨站请求伪造。

### 7.2 回程登出（Back-Channel Logout）

管理员在应用配置中填写「回程登出地址」（生产环境必须 https 且不得指向回环/私网地址）。用户在门户登出、RP 发起登出确认、管理员强制下线或取消授权时，门户会向该地址 POST `application/x-www-form-urlencoded` 的 `logout_token`：

```json
{
  "iss": "https://auth.example.com",
  "aud": "YOUR_CLIENT_ID",
  "sub": "<user uuid>",
  "sid": "<门户会话 uuid>",
  "iat": 1780000000,
  "exp": 1780000120,
  "jti": "<唯一标识>",
  "events": {
    "http://schemas.openid.net/event/backchannel-logout": {}
  }
}
```

接收方必须：

- 用 JWKS（`kid` 选钥）验签，校验 `iss` 等于门户 issuer、`aud` 等于自身 `client_id`。
- 校验 `iat`/`exp` 新鲜窗口（默认 120 秒内），拒绝过期令牌。
- 维护 `jti` 已见缓存防重放；对同一 `jti` 只处理一次。
- 只对 `events` 中存在 `http://schemas.openid.net/event/backchannel-logout` 的令牌执行登出。
- 终止本地与 `(sub, sid)` 匹配的会话；id_token 中的 `sid` 即门户会话标识，登录时请按 `(sub, sid)` 绑定本地会话。
- 处理成功返回 2xx；门户对失败会有限重试，但仍以“尽力而为”为准，不能假设一定送达。

### 7.3 浏览器串跳漏斗（无回程通道的网站）

如果你只配置了「登出地址」（`logout_uri`）而没有回程地址，门户登出时会向浏览器返回形如：

```text
https://your-site.example/logout?next=<下一个目标或门户登录页的 URL 编码值>
```

你的 `logout_uri` 端点应：清掉本地会话，随后 302 到 `next`；出于安全，只允许相对路径或自己的域名，拒绝 `//` 开头的外部协议重定向。

## 8. acr 声明

`id_token` 携带 `acr`：

- `urn:lipass:acr:1fa`：仅密码登录
- `urn:lipass:acr:2fa`：经过邮箱验证码 / TOTP / 恢复码二次验证

> 品牌改名前的历史令牌在过期前仍携带 `urn:portal-oss:acr:1fa/2fa`；
> 升级期间按“两套值等价”校验，窗口过后只保留 `urn:lipass:acr:*`。

需要强认证的网站可校验该声明，拒绝 1fa 会话。

## 9. 安全要求

- 必须校验 `state` 与 `nonce`。
- 公开客户端必须使用 PKCE；机密客户端在服务端保管 secret。
- `redirect_uri` 必须精确匹配门户白名单。
- 授权码只能使用一次，10 分钟有效。
