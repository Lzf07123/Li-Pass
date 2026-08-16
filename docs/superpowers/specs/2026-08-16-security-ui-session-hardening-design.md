# 安全、UI 与会话守护全量加固设计

## 1. 目标

把三轮对照审查（安全与逻辑、UI、会话守护）确认的 **P0/P1/P2 缺陷与加固项** 一次性落地，使 Li&Pass 在
缺陷层面达到主流 IdP（Keycloak / Auth0 / Authelia）的基准。纯新增生态能力（refresh token、revocation、
prompt/max_age、WebAuthn、动态注册、SAML 等）**不在本设计范围**，记录为后续路线图。

## 2. 现状与约束

- 现状见三轮审查结论与本文件 §5 对照表；测试基线：后端 OIDC 相关 30 项、前端 138 项全绿。
- 硬约束：安全不降级、破坏性变更进 CHANGELOG 且可迁移、数据库变更需 Alembic 迁移、
  UI 遵循 design-system 与 `prefers-reduced-motion`、OIDC 契约变更同步 `docs/oidc-integration.md`。

## 3. 方案与取舍

### 3.1 认证与凭证（后端）

- **登录账号枚举时序**：邮箱不存在时对固定 dummy Argon2 哈希执行一次 `verify_password`，抹平耗时差。
  固定哈希在模块导入时生成一次（Argon2 参数沿用默认配置，成本可接受）。
- **登录/注册 CSRF**：现有 Origin 校验只在「带会话 Cookie」时生效。改为对
  `POST /api/v1/auth/login` 与 `POST /api/v1/auth/register` 也在 **Origin 存在且不在白名单** 时拒绝
  （缺失 Origin 的 curl 等非浏览器客户端保持放行，与现状一致）。
- **可信设备撤销一致性**：自我重置密码、管理员重置密码、管理员重置 2FA 三条路径统一调用
  `revoke_all_trusted_devices`，与「修改密码/退出所有设备」一致，消除 2FA 旁路。
- **恢复码熵**：`token_hex(8)`（64 bit）→ `token_hex(16)`（128 bit）；HMAC 落库方式不变。
- **后端 CSP**：追加 `object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'`。

### 3.2 OIDC 合规（后端）

- **PKCE 全客户端强制**：token 端点删除「机密客户端免 PKCE」分支，统一校验 `code_verifier`。
  authorize 端点本就要求 `code_challenge`，因此机密客户端无兼容冲击（OAuth 2.1 对齐）。
- **token 端点错误格式**：由 `{"detail": "..."}` 改为 RFC 6749 的 `{"error": "...", "error_description": "..."}`
  并保留 HTTP 状态码。authorize 端点已是标准 `error` 回跳；userinfo 与 `/oauth2/client/*`
  维持 `detail`（管理/黑名单 API 非 OAuth 端点）。
- **id_token 增加 `at_hash`**：token 端点同时签发 access_token 与 id_token 时必填
  （OIDC Core §3.3.2.11），值为 `base64url(SHA256(access_token)[:16])`。
- **nonce 为空时省略 claim**：不再输出 `"nonce": null`。
- **发现文档补齐**：`token_endpoint_auth_methods_supported: ["none", "client_secret_post"]`、
  `claims_supported: ["sub","email","email_verified","nickname","name","picture","acr","sid"]`。
- **参数长度上限**：authorize 的 `nonce`(≤255)、`state`(≤512)、`code_challenge`(≤255)、
  `redirect_uri`(≤1000)、`client_id`(≤128)、`scope`(≤500) 在路由层校验，杜绝 PostgreSQL
  VARCHAR 超长导致的 500。
- **回调拼接**：`build_authorize_redirect` / `redirect_error` 对已含 `?` 的 redirect_uri 改用 `&`
  追加参数（当前 `?foo=bar?code=...` 是确定性 bug）。
- **授权请求绑定用户**：`PendingAuthRequest` 增加 `user_id`；authorize 创建时写入，
  consent approve/deny 校验与当前会话用户一致，否则 403，防止跨账号串号授权。
- **端点限流**：`/oauth2/token` 与 `/oauth2/authorize` 增加按 IP 限流
  （新配置 `TOKEN_RATE_LIMIT`、`AUTHORIZE_RATE_LIMIT`，默认 120/分钟，仅防滥用/DoS）。

### 3.3 会话守护（后端）

- **空闲超时粒度**：`SESSION_IDLE_DAYS`（整数天）→ `SESSION_IDLE_MINUTES`（整数分钟，默认 720）。
  全部读取点（deps、用户/管理员会话清理）同步改为 `timedelta(minutes=...)`；配置校验 ≥5。
  属破坏性配置变更：旧 `SESSION_IDLE_DAYS` 环境变量失效，升级说明写入 CHANGELOG 与部署文档。
- **`GET /api/v1/me/session`**：返回 `{session_id, expires_at, last_used_at, idle_limit_minutes}`，
  供前端做空闲提醒（响应本身走 `_load_identity`，天然刷新 `last_used_at`）。
- **回程登出 DNS 固定**：解析安全校验通过后，把解析出的公网 IP 列表固定给连接层
  （自定义 `httpcore.SyncBackend` + `ConnectionPool` 的公开 API，重写 `connect_tcp` 按固定 IP 拨号，
  TLS SNI/证书校验仍用原域名），消除「校验解析」与「实际连接」之间的 rebinding 窗口。
  MockTransport 注入路径保留，测试不受影响；私网/回环校验逻辑不变。
- **回程登出地址校验**：拒绝 URL 中的 fragment。

### 3.4 前端 UI 与安全

- **移除「记住密码」**：删除 localStorage 密码持久化，只保留「记住账号」；
  `remember_me`（服务端会话 TTL）不受影响。属破坏性行为变更。
- **CSP 与首帧**：index.html 的内联主题脚本/样式在生产 CSP 下会被拦截。改为
  `public/theme-init.js`（阻塞加载、首帧前应用主题）与 `public/preflight.css`，
  index.html 改为外链引用；nginx CSP 增加 `script-src 'self'` 显式声明、
  `img-src` 追加 `https:`（放行客户端 logo，配合 no-referrer 不泄露路径）。
- **全局 401 兜底**：api 客户端对「非 /api/v1/auth 前缀」的 401 派发
  `lipass:unauthorized` 事件；App 监听后携带 `next` 跳转登录，消除会话被吊销后
  敏感数据滞留屏幕的问题。Dashboard/Admin 首次 `/me` 失败同样回传 `next`。
- **授权确认页身份展示**：`GET /api/v1/consent/{id}` 返回当前用户 email/nickname，
  页面展示「正在以 xxx 登录」；新增 `POST /api/v1/auth/logout/local`（只吊销当前门户会话、
  不派发回程登出、不串跳），支持「使用其他账号登录」后带着 `next=/consent?request_id=...` 重新登录。
- **空闲提醒**：基于 `/me/session` 的 `idle_limit_minutes` 与 `last_used_at`，页面活动（节流 30s）
  重新同步；剩余 5 分钟弹提示，倒计时归零跳转登录（`next` 保留）。`prefers-reduced-motion` 下无动画。
- **小项**：Modal 焦点陷阱（Tab 循环）；登录邮箱输入 `autoComplete="username"`；
  站内信铃铛接 `visibilitychange`/`focus` 刷新（防抖）。

### 3.5 明确不在本设计范围（后续路线图）

refresh token / revocation endpoint / introspection、`prompt`/`max_age`/`login_hint`、WebAuthn、
密码策略（pwned/历史）、渐进式暴力破解锁、会话 IP 绑定与并发上限、令牌轮换、动态客户端注册、SAML。

## 4. 接口与数据模型变更

- 无数据库迁移（不新增列/表）。
- 配置：删除 `SESSION_IDLE_DAYS`，新增 `SESSION_IDLE_MINUTES`、`TOKEN_RATE_LIMIT`、
  `AUTHORIZE_RATE_LIMIT`。
- API：新增 `GET /api/v1/me/session`、`POST /api/v1/auth/logout/local`；
  `GET /api/v1/consent/{id}` 响应增加 `user` 字段；`/oauth2/token` 错误体改 RFC 6749 格式。

## 5. 安全影响

全部为加固方向：消除枚举时序、登录 CSRF、可信设备 2FA 旁路、rebinding 窗口、明文密码落盘、
会话吊销后的数据滞留；提升 OIDC 互操作（错误格式、at_hash、PKCE、元数据）。无新增攻击面；
`img-src https:` 允许加载第三方 logo，属可控放宽（无 Referrer 泄露）。

## 6. 验收标准

- 后端：`python -m pytest -q` 全绿（新增/更新的失败测试先行：红→绿）。
- 前端：`npx tsc -b && npm run lint && npm test && npm run build` 全绿。
- 行为抽查：token 错误体含 `error`/`error_description`；id_token 含 `at_hash` 且
  `at_hash == base64url(sha256(access_token)[:16])`；机密客户端缺 verifier 被拒；
  密码重置后可信设备列表为空；dummy-hash 登录路径耗时接近真实路径；
  生产 CSP 下主题脚本可执行（构建产物外链、无内联）。
- 编排：`docker compose --profile bundle config -q` 通过。

## 7. 风险

- token 错误格式与 PKCE 全强制属于 OIDC 行为变更：docs/oidc-integration.md 与 demo 站同步；
  旧接入方若自行解析 `detail` 需按文档更新。
- `SESSION_IDLE_MINUTES` 改名属配置破坏性变更，需在 CHANGELOG「破坏性变更」说明迁移。
- 「移除记住密码」属用户可见行为变更，需说明原因与替代（浏览器密码管理器）。
