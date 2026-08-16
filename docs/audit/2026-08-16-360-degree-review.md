# Li&Pass 全栈 360° 审查报告（2026-08-16）

> 审查对象：仓库 `main`（30c0ed8）。方式：全新 Docker 栈（`bundle` + `demo`）真机运行 + 逐行代码审查 + 边界实测。所有结论均附代码位置或可复现输出。

## 1. 执行摘要

结论：**整体安全设计成熟，认证/OIDC/会话体系未发现高危漏洞；发现 1 个中危（登录 CSRF 缺口）与 1 个低危缺陷（并发注册 500），另有 8 项低危/信息级建议。** 建议优先修复中危项后即可继续发布。

审查环境：

- 全新栈：`docker compose --profile bundle --profile demo up -d --build`，18 个 Alembic 迁移干净执行，`healthz`/`readyz`/发现文档正常。
- 测试账号：`audit-user@example.org`（普通）、`audit-admin@example.org`（管理员）、`delete-me@example.org`（注销流程用后已删除）。
- 邮件后端临时以 `EMAIL_BACKEND=console` 覆盖启动（不改 `.env`），验证码取自后端日志；SMTP 代码路径做静态审查。
- 验证基线：后端 `pytest` 490 通过；前端 `tsc -b` + `oxlint` + `vitest` 146 通过 + 生产构建通过；`alembic downgrade -1 && upgrade head` 真实 PostgreSQL 往返通过；`pip-audit`（运行时依赖）与 `npm audit --omit=dev` 均为 0 漏洞。

## 2. 发现问题（按严重度）

> **修复状态（2026-08-16 第二轮，分支 `codex/audit-fixes-round2`）**：全部条目已修复并提交。2.1→`8a4355d`；2.2→`6318c92`；2.3→`11b578d`；2.4→`ddfc2a4`；2.5/2.6→`a8ab448`（含迁移 `b7e8f9a0c1d2`）；2.7→`3e0eecf`；信息级第 1 项→`c7614fc`、第 2 项→`48bff9a`（生产仅 https）、第 4 项→`fbce50e`、第 5/6 项→`b9103cc`；信息级第 3 项为运维说明（记录于 CHANGELOG/deployment.md），第 3 项外链头像的「跨站像素追踪」本质无法在 IdP 侧根除（URL 为用户自选、`Referrer-Policy: no-referrer`），以协议收紧 + 文档记录收口。

### P1 高危

未发现。

### P2 中危

#### 2.1 登录 CSRF：`/2fa/verify` 未纳入 Origin 白名单守卫

- 位置：[backend/app/main.py](backend/app/main.py:153) `_origin_guarded_auth_paths` 只含 `/api/v1/auth/login` 与 `/api/v1/auth/register`；[backend/app/api/routes/auth.py](backend/app/api/routes/auth.py:682) `verify_twofa` 成功后直接 `_create_session_and_cookie` 下发 `lipass_session`。
- 攻击链：攻击者用自己的密码登录取得 `challenge_id`，获取自己的 2FA 验证码，诱导受害者浏览器向 `POST /api/v1/auth/2fa/verify` 提交（HTML 表单跨站 POST，此时浏览器无门户会话 Cookie → `guarded` 判定为 false → 不校验 Origin）。受害者浏览器被写入攻击者账号的会话 Cookie，随后访问门户即处于攻击者账号内（登录串号，可导致受害者把敏感数据写入攻击者账号、误以为在用自己的账号）。
- 实测证据：

```text
POST /api/v1/auth/2fa/verify   Origin: http://evil.example（无会话 Cookie）
→ HTTP 200，响应 Set-Cookie: lipass_session=...
```

而同样携带恶意 Origin 的 `/login`、`/register`、带会话的写请求均正确返回 403。

- 修复建议：把 `/api/v1/auth/2fa/verify` 加入 `_origin_guarded_auth_paths`；建议连带 `/api/v1/auth/2fa/send`、`/api/v1/auth/email/verify` 一并纳入（防御性），或改为「凡响应会 Set-Cookie 的写请求一律要求 Origin 白名单」。

### P3 低危

#### 2.2 并发注册同一邮箱触发未捕获 IntegrityError（HTTP 500）

- 位置：[backend/app/api/routes/auth.py](backend/app/api/routes/auth.py:182) `db.add(user); db.commit()` 无 `IntegrityError` 捕获（对比邀请注册路径 [auth.py](backend/app/api/routes/auth.py:385) 有捕获）。
- 实测：两个并发 `POST /api/v1/auth/register`（同邮箱 `race@example.org`）→ 一个 201、一个 500；后端日志 `UniqueViolation: duplicate key value violates unique constraint "ix_users_email"`。无数据损坏（唯一索引兜底），但产生 500 与错误噪音，也与「重复注册不报错」的枚举抹平意图不一致。
- 修复建议：捕获 `IntegrityError` 后与「已注册」路径返回相同成功文案（可保留一次同参数 Argon2 哈希以维持时序抹平）。

#### 2.3 演示站登出漏斗断链

- 位置：[examples/demo-site/app.py](examples/demo-site/app.py:147) `/logout` 只接受相对路径 `next`，而门户 `build_logout_funnel` 生成的 `next` 是绝对 URL 链。
- 实测：`GET /demo/logout?next=http%3A%2F%2Flocalhost%2Flogin` → `Location: /demo/`，串跳在 demo 站中断、无法回到登录页。仅影响演示站，不影响门户核心。

#### 2.4 回程登出 SSRF 校验未拒绝 IPv4-mapped IPv6

- 位置：[backend/app/services/federated_logout.py](backend/app/services/federated_logout.py:25) `_is_unsafe_ip` 使用 `is_private/is_loopback/...`；Python 对 `::ffff:127.0.0.1`、`::ffff:10.0.0.1` 这类 IPv4-mapped IPv6 的上述判断返回 False，可绕过公网校验并被固定到连接层。
- 前置条件：仅管理员能配置回程地址，且生产强制 https + 443，属纵深防御缺口。
- 修复建议：在 `_resolve_public_host` 中先把 `ipaddress.ip_address()` 结果的 `ipv4_mapped` 还原为 IPv4 再校验（`geoip.normalize_ip` 已有同类处理可复用）。

#### 2.5 恢复码兼容旧裸 SHA-256 分支长期保留

- 位置：[backend/app/services/twofa.py](backend/app/services/twofa.py:186)。旧版 64-bit 熵恢复码永远可用裸 SHA-256 路径消费；建议确定迁移窗口后移除该分支，并强制旧用户重新生成恢复码。

#### 2.6 HMAC 密钥复用 Fernet 加密密钥文件

- 位置：[backend/app/security/crypto.py](backend/app/security/crypto.py:69)。OTP/恢复码 HMAC 与 Fernet 数据加密共用同一密钥材料，密钥用途未分离。建议用 HKDF 按用途派生独立密钥（低危、crypto hygiene）。

#### 2.7 服务端密码策略只有长度下限（8–128）

- 位置：[backend/app/schemas/auth.py](backend/app/schemas/auth.py:9)。无服务端复杂度/常见口令校验，强度仅前端展示（CHANGELOG 声明为有意）。作为安全产品，建议增加服务端最低复杂度或弱口令清单拒绝，避免仅靠前端约束。

### 信息级 / 一致性建议

1. 用户侧 `GET /api/v1/sessions` 与 `GET /api/v1/apps` 未按空闲超时过滤（管理端统计已修），空闲但未触发的会话仍显示为在线——展示口径不一致。
2. `PUT /api/v1/me` 允许任意 http(s) 外链头像，可被用于跨站像素追踪（前端 CSP `img-src https:` 放行）；属可接受范围，建议知会用户并考虑仅允许白名单外链。
3. dev 环境 memory 存储 + uvicorn `--limit-max-requests 10000`：worker 重启会清空限流计数与进行中的 2FA 挑战/待授权请求（生产配置校验强制 redis，不受影响）。
4. `GET /oauth2/userinfo` 401 未带 `WWW-Authenticate` 头（RFC 6750 建议）；属合规性小项。
5. `GuestOnly` 对绝对 URL 的 `next`（同源 OIDC 授权 URL）走 React Router 内部跳转可能落到首页而非恢复授权流——边缘 UX，无开放重定向风险。
6. 注册成功 toast 文案「注册成功」与实际语义「已受理，请验证邮箱」略有出入。

## 3. 已验证正确的关键防线（正面清单）

### 认证与 2FA

- Argon2id 哈希、`password_needs_rehash` 自动升级；登录/注册枚举时序抹平（不存在的邮箱同参哈希）— [auth.py](backend/app/api/routes/auth.py:57)。
- 三层登录限流（email+IP / 全局 email / IP）实测：第 6 次错误密码返回 429。
- 强制 2FA：验证邮箱即启用邮箱验证码；2FA 挑战 5 次锁定实测（第 6 次「验证码错误次数过多」）；成功消费验证码不占限流额度。
- 恢复码 128-bit 熵、HMAC 落库；TOTP `valid_window=1`；关闭最后一种 2FA 被拒。

### 会话与可信设备

- 会话 Cookie `HttpOnly / SameSite=Lax / 生产 Secure`；服务端空闲超时 + 5 分钟低频刷新 `last_used_at`；过期会话自动吊销 — [deps.py](backend/app/api/deps.py:66)。
- 撤销即时生效实测：撤销后旧 Cookie 访问 `/me` → 401。
- step-up 30 分钟窗口按会话隔离实测：无密码复核 403 / 错密码 400 / 正确后放行，窗口内后续操作免密。
- 可信设备实测：7 天 Cookie 属性正确（HttpOnly/Max-Age=604800/Path/SameSite），登出后重登免 2FA；密码重置后设备被吊销（重新要求 2FA）。

### OIDC

- PKCE S256 对全部客户端强制：错误 verifier → `invalid_grant`；verifier 长度 43–128 强制。
- 授权码单次消费 + 原子条件更新：并发换码实测 1 成功 1 失败；同码重放被拒。
- `id_token`：`at_hash` 实测正确、`acr=urn:lipass:acr:2fa`、`sid` 与链接一致、`aud=client_id`；`access_token aud=userinfo 端点`；userinfo 按 scope 裁剪 claims。
- 机密客户端：无/错 secret → 401 `invalid_client`，正确 secret + PKCE → 200；token 端点错误格式对齐 RFC 6749。
- authorize 非法参数（未知 client / 非法 redirect_uri / 非法 response_type / 非法 scope）均回跳门户错误页，不产生开放重定向。
- 回程登出：DNS 固定 + 公网校验 + 无凭据/无片段/生产 https 443；登出确认绑定 `sid` 实测（跨会话确认 404）。
- RP 发起登出回跳白名单实测：白名单外回跳被拒。

### CSRF / 越权 / 输入

- `Origin` 白名单校验实测：`/login`、`/register`、带会话写请求携带 `Origin: http://evil.example` 均 403（缺口见 2.1）。
- `TrustedHostMiddleware` 实测：`Host: evil.example` → 400。
- 头像路径穿越 `../` → 422；静态 `uploads` 404 返回 `no-store`。
- 普通用户访问全部 `/api/v1/admin/*` → 403；管理端角色变更/重置密码/重置 2FA/删除客户端等敏感操作有 step-up 门禁（实测无密码 403、错密码 400、正确放行）；管理端删除用户要求密码+2FA 且禁止删除管理员/自身。
- 客户端自助黑名单 Basic 认证（错凭据 401）+ 三层拦截实测：被封禁用户 authorize → `access_denied&error_description=account_blocked`。

### 账号生命周期

- 注册→邮箱验证→登录→2FA→会话全链路实测通过。
- 更换登录邮箱实测：错误密码 400、错误验证码 400、成功后 `sub`（UUID）不变、新邮箱生效。
- 密码重置实测：旧会话立即 401、可信设备吊销、审计落账。
- 注销实测：仅密码不带 2FA → 400；密码+邮箱验证码 → 成功、审计 `user_delete_self` 落账、注销后无法登录。

### 基础设施与依赖

- 网关 nginx：单域名入口、`/demo` 前缀 rewrite 实测（`/demo/` 200、`/demo/login` 302）、上传 6m 上限、安全头齐全；前端 nginx CSP `script-src 'self'`、`style-src 'self'`、无 `unsafe-inline` 样式块。
- `--proxy-headers --forwarded-allow-ips 172.30.0.10`：限流取真实客户端 IP，而非全部视作网关。
- 迁移：真 PG `alembic downgrade -1 && upgrade head` 往返通过。
- 依赖：后端运行时依赖 `pip-audit` 0 漏洞（venv 内开发工具 pip/pytest 有新版可用，非运行时）；前端生产依赖 `npm audit` 0 漏洞。

## 4. 审查范围外的限制（未验证项）

- 真实 SMTP 发信未实测（本次以 console 后端运行；SMTP 代码含 TLS 证书校验、超时、重试与批量单连接，经静态审查）。
- `SESSION_IDLE_MINUTES=10080`（7 天，来自本机 `.env`）的空闲下线未等待实测，依赖代码审查与现有测试套件。
- 生产 HTTPS 部署形态（外层 TLS 终结、Secure Cookie、HSTS）未在本机验证。
- 未做大规模并发/性能压测；未做真实浏览器自动化 E2E（前端守卫/跳转主要依据 146 个单测 + 代码审查）。

## 5. 建议处置顺序

已全部完成（见第 2 节顶部的修复状态）。后续建议：

1. 在真实生产 HTTPS 环境做一轮冒烟（Secure Cookie/HSTS/外层 TLS），本机审查未覆盖。
2. 若存量部署中存在旧恢复码用户，升级时提前公告「恢复码作废、需重新生成」。
3. 信息级第 3 项（memory 存储 + worker 重启）保持开发环境已知行为，生产配置校验已强制 redis，无需代码变更。

## 附录 A：复现命令（关键项）

```bash
# 2.1 登录 CSRF 缺口（应期望 403，实际 200 + Set-Cookie）
curl -sS -c /tmp/csrf.cookies -X POST http://localhost/api/v1/auth/2fa/verify \
  -H 'Content-Type: application/json' -H 'Origin: http://evil.example' \
  -d '{"challenge_id":"<攻击者挑战ID>","method":"email_otp","code":"<攻击者验证码>"}'

# 2.2 并发注册竞态（应期望两个同文案成功，实际其一 500）
( curl -sS -X POST http://localhost/api/v1/auth/register -H 'Content-Type: application/json' \
    -d '{"email":"race@example.org","password":"Race#2026Test!","nickname":"甲"}' &
  curl -sS -X POST http://localhost/api/v1/auth/register -H 'Content-Type: application/json' \
    -d '{"email":"race@example.org","password":"Race#2026Test!","nickname":"乙"}' & wait )
```

## 附录 B：环境与账号状态

- 审查结束后栈保持运行；测试账号：`audit-user2@example.org`（已改邮箱，密码 `NewAudit#2026Pass!`）、`audit-admin@example.org`（密码 `Audit#2026Test!`）、`race@example.org`（注册竞态残留）。
- 重建前对旧开发库的备份：`backups/pre-audit-2026-08-16.dump`。
