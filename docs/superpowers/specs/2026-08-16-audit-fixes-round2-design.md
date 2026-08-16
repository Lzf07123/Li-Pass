# 360° 审查问题修复设计（第二轮）

## 目标

逐项修复 [360° 审查报告](../../audit/2026-08-16-360-degree-review.md) 中全部可行动项：1 个中危（登录 CSRF）、1 个低危缺陷（并发注册 500）、5 个低危加固项与 6 个信息级一致性/合规项，保持既有防护与测试基线不降级。

## 现状与方案

### 1. 登录 CSRF（中危）

- 现状：`main.py` 的 `_origin_guarded_auth_paths` 只含 `/login`、`/register`；`POST /api/v1/auth/2fa/verify` 成功后 `_create_session_and_cookie` 下发会话 Cookie，但携带恶意 Origin 且无会话 Cookie 时不校验 Origin。
- 方案：把 `/api/v1/auth/2fa/verify`（会 Set-Cookie）与 `/api/v1/auth/2fa/send`、`/api/v1/auth/email/verify`（防御性）加入守卫集合。不改变浏览器/curl 行为（缺失 Origin 仍放行）。
- 安全影响：堵住「攻击者用自己挑战+验证码把受害者浏览器登录进攻击者账号」的登录串号路径。

### 2. 并发注册 500（低危）

- 现状：`auth.register` 在 `db.add(user); db.commit()` 处不捕获 `IntegrityError`，并发同邮箱注册时一个请求 500（唯一索引兜底，无数据损坏）。
- 方案：捕获 `IntegrityError` 后 `rollback`，执行一次同参数 Argon2 哈希保持时序抹平，返回与「已注册」相同的受理文案。

### 3. 回程登出 SSRF：IPv4-mapped IPv6（低危）

- 现状：`federated_logout._resolve_public_host` 对 `::ffff:127.0.0.1` 等 IPv4-mapped IPv6 的 `is_private/is_loopback` 判断返回 False，可绕过公网校验。
- 方案：抽取 `_normalize_resolved_ip`/`_validate_public_addresses`，先把 `ipv4_mapped` 还原为 IPv4 再做危险网段校验；`_resolve_public_host` 复用。

### 4. 恢复码弱哈希兼容分支 + HMAC 密钥域分离（低危）

- 现状：`twofa.consume_recovery_code` 保留旧版裸 SHA-256 存储的兼容分支；`crypto.hmac_hex` 与 Fernet 加密复用同一密钥文件（OTP/恢复码 HMAC 与数据加密未域分离）。
- 方案：
  - 移除裸 SHA-256 兼容分支；
  - `_hmac_key` 从加密密钥派生独立 HMAC 密钥（`HMAC(master, b"lipass:hmac:v2")`，域分离）；
  - 新 Alembic 迁移清空 `recovery_codes` 表：旧弱哈希行与新 HMAC 密钥下失效的行无法区分，统一作废并强制重新生成（未发布版本，破坏性变更按 AGENTS 流程记录）；downgrade 为 no-op。
- 影响：存量恢复码作废（重新开启 TOTP 即可重生成）；未消费 OTP 随密钥切换失效（10 分钟内自然过期，用户重新获取）。

### 5. 服务端密码策略（低危）

- 现状：服务端只有长度 8–128 约束，复杂度仅前端展示。
- 方案：`security/passwords.py` 增加 `password_meets_policy`/`validate_password_strength`：长度 ≥8 且 4 类字符（小写/大写/数字/符号）至少 2 类，与前端「中」档口径一致。挂到注册、邀请注册、重置密码、修改密码、管理端代建/重置密码的密码字段。

### 6. 头像外链协议（信息级）

- 方案：`ProfileUpdate.avatar_url` 外链在开发环境允许 http(s)，生产环境仅允许 https（与 `_validate_web_url` 的既有模式对齐）。本地上传路径形态不变。

### 7. userinfo 401 补 WWW-Authenticate（信息级）

- 方案：`GET /oauth2/userinfo` 的 401 响应带 `WWW-Authenticate: Bearer realm="userinfo"`（RFC 6750）。

### 8. 会话/应用列表空闲口径一致（信息级）

- 方案：`GET /api/v1/sessions` 过滤已过期/空闲超时会话；`GET /api/v1/apps` 的 `active_sessions` 计数额外要求 `last_used_at` 在空闲窗口内，与管理端统计口径一致。

### 9. 演示站登出漏斗（低危）

- 方案：`examples/demo-site/app.py` 的 `/logout` 接受「相对路径」或「与 ISSUER 同源的绝对 http(s) URL」作为 `next`，跟随门户生成的绝对 URL 串跳链；其余回退自身首页（无开放重定向）。无独立测试基建，以重建后的 curl 实测验收。

### 10. 前端跳转与文案（信息级）

- `GuestOnly`：已登录且 `next` 为安全绝对 URL 时改用 `window.location.replace` 恢复授权/跳转（此前 React Router 内部解析会落到首页）。
- 注册成功 toast 文案改为与后端语义一致：「注册请求已受理，请查收邮箱验证码后完成验证」。

### 11. 文档与运维说明

- CHANGELOG 按分区记录（破坏性变更：恢复码作废；安全加固：CSRF/SSRF/密码策略等；行为变更：生产外链头像 https；缺陷修复：并发注册 500、demo 漏斗；运维工具：dev memory 存储 + worker 重启说明）。
- docs/deployment.md 环境变量表补充 `UVICORN_WORKERS`/memory 存储与 `--limit-max-requests` 的说明。

## 验收标准

- 后端全量 pytest 通过（含每项新增的失败-通过测试）；前端 tsc/lint/test/build 通过。
- 真实 PostgreSQL `alembic downgrade -1 && upgrade head` 往返通过。
- Docker 重建后 curl 复测：恶意 Origin 的 2FA/邮箱验证返回 403；并发注册无 500；demo 登出漏斗跟随绝对 next；userinfo 401 带 WWW-Authenticate。
