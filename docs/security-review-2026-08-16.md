# Li&Pass 全面安全审查报告（2026-08-16）

> 审计方式：真实 Docker 全新栈 + 静态代码审查 + 动态接口实测。
> 结论先行：未发现可直接导致账号接管、数据泄露或 OIDC 越权的高危漏洞；
> 认证与 OIDC 主链路、CSRF/限流/审计/联邦登出防护整体扎实。发现 4 个中等级
> 问题与若干低等级加固点，均给出复现路径与修复建议。

## 0. 修复状态（2026-08-16 追加）

本报告 A/B 系列问题已全部修复并验证（新增回归测试 + 真实浏览器端到端验证）：

- ✅ A1 登出确认请求绑定发起会话（confirm/local-only 校验 sid，跨会话 404）
- ✅ A2 compose `LOGIN_EMAIL_RATE_LIMIT` 默认 20→10（容器实测生效 10）
- ✅ A3 手机号重复绑定 500→409
- ✅ A4 头像目录启动时创建、缺失文件 404；`/uploads` 仅 200 长缓存、错误 no-store
- ✅ B1 客户端 scope 白名单（openid/profile/email，必须含 openid）
- ✅ B2 `ClientUpdate` 拒绝空 `redirect_uris`/`scopes`
- ✅ B3 token 端点表单长度上限；PKCE verifier 43–128、challenge 格式校验
- ✅ B4 邮件发送失败 502→503
- ✅ B5 `.env` 废弃 `SESSION_IDLE_DAYS` → `SESSION_IDLE_MINUTES=10080`；
  deployment 文档迁移 head 更新为 `6e7f8a9b0c1d`
- ✅ 额外发现并修复：访客访问注册/找回/重置页被全局 401 兜底弹回登录页
  （`GuestOnly` 改用静默会话探针）

验证证据：后端 pytest 473 通过（含 14 个新回归测试）；前端 tsc/lint/vitest
145 通过 + 生产构建成功；无头 Chrome 全 UI 跳转端到端 46/46 通过（静态路由、
访客互跳、注册→登录、邮箱验证、登出→2FA、管理后台 8 标签、站内信、
OIDC 授权回跳、RP 登出回跳、401 兜底、邀请注册、找回密码）。

B6（密码复杂度策略）与 B8（状态变更纳入 step-up）属产品策略取舍，未在本次改动；
B7 的 PKCE 格式校验已随 B3 一并落地。本机 SMTP 凭据（526 认证失败）需运维侧更换。

## 0.1 第二轮全量审查补充（2026-08-16）

覆盖面：后端剩余服务（email/geoip/device_info/blocks/site_settings/notifications/
maintenance/avatar_cleanup/system_info/admin_stats/ip2region_update）、core/db 与
redis、剩余模型、全部 19 个 Alembic 迁移（含 downgrade）、运维脚本
（make_admin/demote/rotate_jwt_key/download_ip2region/backup/restore）、CI、
前端 DashboardPage 全量与 8 个管理面板、Modal/ConfirmDialog/MessageBell/
StepUp2faForm/useStepUp/useAsyncAction/ToastProvider、vite/package 构建配置。

结论：未发现新的中/高危问题；认证与数据层防护扎实。新增低危项与观察：

- ✅ 已修复：黑名单接口畸形 `user_id` 返回语义错位的 409（UUID 转换异常被
  `except ValueError` 误捕获）。现 `ClientBlockCreate.user_id` 用 UUID 类型校验，
  畸形输入返回 422；TDD 红绿验证 + 全量 474 测试通过。
- ✅ 已修复：管理后台统计「在线会话」与「在线会话认证方式分布」补上空闲超时
  过滤（`last_used_at` 需在 `SESSION_IDLE_MINUTES` 窗口内），与其它在线口径一致。
- ✅ 已澄清（无偏移，无需改数据）：迁移 `a1b2c3d4e5f6` 的 timestamp→timestamptz
  转换发生在项目早期，当时编排尚未引入 `TZ=Asia/Shanghai`（git 历史显示该配置
  在后续重命名提交才加入），写入与改列均在同一 UTC 会话时区下完成，存量
  “UTC naive” 值按 UTC 重解释，**不产生 8 小时偏移**。非标准部署（曾混用不同
  会话时区）可用部署文档新增的核查 SQL 抽检。
- ✅ 已修复：`ClientBlockCreate.email` 改为 `EmailStr` 格式校验，畸形邮箱返回
  422，避免脏数据落库。
- [观察] 「站点设置/公开注册开关」「禁用/启用用户」「修改客户端配置」不需要
  step-up 密码复核（与既有敏感操作清单一致，属设计取舍）。

正向确认：邮件 HTML 模板对动态内容全量转义；Modal 有焦点陷阱/Escape/背景关闭；
AsyncButton 防重复提交；useStepUp 以后端为权威判定；geoip/设备解析对损坏数据
容错；全部迁移 downgrade 完整（1 处文档化的 no-op）；备份脚本 `set -euo pipefail`、
恢复需交互确认。第二轮验证证据：后端 pytest 474 通过、前端 tsc/lint/145 测试通过。

## 1. 审计范围与方法

- 事实来源：README / CHANGELOG / docs/deployment.md / docs/oidc-integration.md / git 历史。
- 静态审查：后端 15 个路由模块、19 个模型、核心 security/services 层、网关 nginx、
  前端 App/API 客户端/守卫/Hook/关键页面、Dockerfile 与 compose。
- 动态验证：全新栈 `docker compose --profile bundle --profile demo up -d --build`，
  注册两个测试账号并走通注册→邮箱验证→密码→2FA→授权→换码→userinfo→登出全链路；
  另覆盖 CSRF/Host、限流、黑名单、可信设备、联邦登出回程、迁移往返等场景。
- 质量门：后端 pytest 461 通过；前端 tsc/lint/vitest 144 通过；pip-audit 与
  npm audit 均 0 漏洞；真实 PostgreSQL 上验证最新迁移 downgrade/upgrade 往返。

## 2. 环境与账号

- 栈地址：http://localhost（gateway :80 唯一入口），六个容器均 healthy。
- 测试账号：
  - `audit.user@example.com` / `Str0ng!Pass#Audit1`（已提权为管理员）
  - `audit2.user@example.com` / `Str0ng!Pass#Audit2`（普通用户，有一台可信设备）
- 测试客户端：`demo-site`（种子）、`cli_IZ8y…`（机密客户端，回程地址指向演示站）、
  `cli_Cylgx…`（公开客户端，回调地址列表被清空用于验证缺口）。
- 审计期间未改动任何仓库代码；`backups/pre-fresh-audit-20260816-090212.sql.gz`
  为清空旧栈前的快照；`portal-*` 历史卷未动。

## 3. 发现清单（按严重度）

### 中（建议尽快修复）

#### A1 登出确认请求未绑定发起会话/账号

- 位置：`backend/app/api/routes/oidc.py` 的 `confirm_logout_request` 与
  `local_only_logout_request`；`PendingLogoutRequest` 存有 `sid/sub` 但从未比对。
- 实测复现：账号 A 经 `/oauth2/end-session` 生成确认请求后，账号 B 用自己的会话
  POST confirm → 返回 200 与 A 的回跳地址 + state；效果是把 **B 自己**踢下线、
  A 保持登录，并把 A 的回跳信息返回给 B。`local-only` 端点甚至完全不需要认证
  （无会话也能拿到 `post_logout_redirect_uri?state=…`）。
- 影响评估：`request_id` 为 256 位随机值，不可猜测；被踢的是确认者本人，未造成
  账号接管，故定级为“中偏低”。但属于明确的状态混用逻辑缺陷。
- 修复：confirm 时校验 `pending.sid == str(session.id)`（必要时加 `sub`），不匹配
  返回 403/404；`local-only` 同样要求当前会话且会话匹配。

#### A2 compose 默认值把登录邮箱限流从 10 退回 20

- 位置：`docker-compose.yaml` 中
  `LOGIN_EMAIL_RATE_LIMIT: ${LOGIN_EMAIL_RATE_LIMIT:-20}`。
- 事实：`backend/app/core/config.py` 默认 `login_email_rate_limit=10`，CHANGELOG 与
  docs/deployment.md 均声明“20→10 收紧”；但容器内实测生效值为 **20**。
- 影响：分布式 IP 爆破的全局邮箱限流比文档宣称宽松一倍。
- 修复：compose 默认改为 10（或删除该行，让代码默认值生效），并补一条部署文档勘误。

#### A3 手机号重复绑定触发未捕获 IntegrityError → 500

- 位置：`backend/app/api/routes/users.py` 的 `bind_phone`。
- 实测复现：账号 A 绑定 `+8613800000001` 后，账号 B 用同一号码提交 → HTTP 500，
  后端日志 `psycopg.errors.UniqueViolation: users_phone_key`。
- 修复：提交前查重并返回 409「该手机号已被绑定」；或捕获 IntegrityError 归一为 409。

#### A4 全新栈首次访问头像目录返回 500，且网关缓存错误响应 7 天

- 位置：`backend/app/main.py` 的 `/uploads/avatars` 挂载（`check_dir=False`）、
  `gateway/nginx.conf.template` 的 `location /uploads/`。
- 实测复现：全新卷（头像目录尚不存在）时
  `GET /uploads/avatars/<任意路径>` → 500（`os.stat(self.directory)` FileNotFoundError）；
  目录存在后缺失文件才回到 404。而网关对该 500/404 一律追加
  `Cache-Control: public, max-age=604800`（`add_header ... always`），错误响应可被
  浏览器缓存 7 天。
- 修复：启动时 `mkdir -p` 头像目录（或在挂载处保证目录存在）；网关只对 2xx 加长缓存，
  例如 `map $upstream_status` 区分或改用 `add_header Cache-Control ... always` 前
  判断状态码（nginx 原生不支持条件 add_header，可改由后端对 `/uploads/*` 成功响应
  签发缓存头、网关去掉 `always`）。

### 低（建议排期加固）

#### B1 OAuth client 的 scopes 是自由列表

实测可注册 `["openid","phone"]` 客户端并完成授权、签发令牌，但 userinfo/id_token
从不输出 phone claim，与发现文档“仅支持 openid/profile/email”矛盾。建议在
`ClientCreate/ClientUpdate` 上把 scopes 限制为支持集（并允许子集、至少含 openid）。

#### B2 `ClientUpdate` 允许把 `redirect_uris` / `scopes` 清成空列表

`ClientCreate` 有 `min_length=1`，`ClientUpdate` 没有。实测 PATCH
`redirect_uris: []` 返回 200，客户端随即不可用（authorize 一律
`invalid_redirect_uri`）。建议 Update 同样要求非空（或禁止把唯一回调清空）。

#### B3 token 端点表单参数无长度上限

`/oauth2/token` 的 `code`、`code_verifier`、`client_id`、`redirect_uri` 均为裸
`Form(...)`，超长 `code_verifier` 会被整体 SHA-256 处理。当前靠网关
`client_max_body_size 6m` 兜底；文档支持“直连后端”的部署形态则无 body 限制。
建议与 authorize 端点一致，为 Form 字段加 `max_length`。

#### B4 邮件发送失败统一返回 502

注册/重发验证码/2FA 发码/重置密码/邀请等失败路径返回 `502 Bad Gateway`。
502 语义是“上游网关故障”，会污染网关与监控的 502 指标；应改为 500/503
（服务自身依赖故障），保留用户友好文案。

#### B5 配置与文档漂移（本机与仓库）

- 本机 `.env` 仍含已废弃的 `SESSION_IDLE_DAYS`（`extra="ignore"` 静默忽略，
  实际按 `SESSION_IDLE_MINUTES=720` 生效）；`EMAIL_BACKEND=smtp` 指向阿里企业邮且
  凭据 526 认证失败，导致注册 502。
- 本机 `.env` 把 `PENDING_REQUEST_STORE/TWOFA_STORE/RATE_LIMITER` 设为 `memory`，
  与 compose 默认 redis 不一致（本地单 worker 可用，上线须切回 redis）。
- `docs/deployment.md` 记载迁移 head 为 `6d1f9c0b2e4a`，实际代码 head 为
  `6e7f8a9b0c1d`，文档未随迁移更新。

#### B6 密码策略仅限长度 ≥8

后端只校验 8–128 字符，无组成复杂度；纯数字 8 位可通过。前端强度条仅为展示。
若产品定位需要，建议后端加复杂度/常见口令策略，并同步前端提示。

#### B7 PKCE 参数格式未校验

`authorize` 只校验 `code_challenge` 非空且 method=S256，不校验 43 字符
base64url 格式；`code_verifier` 未限制 43–128。不影响安全性（最终按哈希比较），
属 RFC 7636 严谨性补强。

#### B8 管理端「状态变更/客户端配置修改」不需要 step-up

实测管理员禁用用户无需密码复核（会话即时失效，防护有效）；`PATCH /admin/clients`
（可改回调地址）与 `PUT /admin/settings` 同样无 step-up。与 CHANGELOG 的
敏感操作清单一致，属设计选择；但“禁用高价值账号”“篡改回调地址”同样值得二次确认，
建议纳入 step-up 清单或至少在报告中说明取舍。

### 观察与演进建议

- JWT 用 RSA 2048（RS256）为当前主流，密钥目录轮换已实现；后续可评估 3072 或
  ES256，并缩短最长轮换窗口。
- 登录按 IP 限流把成功登录也计入（20 次/15 分钟），共享出口办公网可能误伤；
  文档已说明权衡，属已知决策。
- 门户登出不撤销当前设备的“可信设备”Cookie（仅改密/退出所有设备撤销），
  与文档一致；若产品预期“登出即撤销信任”，需再讨论。
- `end-session` 解析 `id_token_hint` 时未校验 audience（仅用于提取 aud 定位客户端，
  且已验签+验 iss），可接受，可在解析时顺手补 audience 策略。

## 4. 验证通过的关键安全控制

- 会话：Cookie HttpOnly/SameSite、`lipass_session` 兼容旧名、空闲超时惰性吊销、
  5 分钟低频 last_used 刷新、改密/重置撤销其它会话与可信设备。
- CSRF/Host：带会话写请求 + 登录/注册强制 Origin 白名单（实测 evil Origin 403、
  evil Host 400）；CORS 显式白名单；TrustedHost 中间件。
- OIDC：非法 client/redirect/response_type 一律回门户不带第三方；PKCE S256 全客户端
  强制；授权码一次性（实测重放 invalid_grant）；机密客户端 secret 三态校验；
  `aud`（id_token=client_id、access_token=userinfo 端点）、`acr/sid/at_hash/nonce`
  正确；userinfo 401/403/claims 裁剪正确。
- 黑名单：authorize 跳 `account_blocked`、token/userinfo 403、Basic 自助 API 限流
  闭环（封禁→userinfo 403→解封→恢复）实测通过。
- 联邦登出：RP-initiated 确认、回程 logout_token 签名/aud/events 校验（RP 拒绝
  aud 不匹配并触发后端重试）、成功 204 闭环、浏览器串跳漏斗实测。
- 限流与枚举防护：登录 5 次失败后第 6 次 429；注册/重置/重发统一文案抹平枚举；
  邮件失败回滚 OTP 与限流计数；OTP/恢复码 HMAC 落库、可信设备 SHA-256 落库。
- 前端：无 `dangerouslySetInnerHTML`/eval/`document.write`；localStorage 仅存
  “记住账号”；`next` 跳转白名单校验；401 全局兜底；空闲提醒与 5 分钟预警；
  管理页前后端双重角色守卫；站内信按纯文本渲染（无 XSS）；CSP 生产禁用内联样式。
- 部署：后端/前端容器不映射宿主机端口、非 root 运行、`no-new-privileges`、
  mem/cpu 限额；生产配置强校验（HTTPS/真实域名/强口令/redis 存储）；ip2region
  运行期更新 SHA256 信任清单 + 原子替换 + flock。
- 依赖与迁移：pip-audit/npm audit 0 漏洞；Alembic 最新迁移在真实 PG 上
  downgrade/upgrade 往返通过。

## 5. 审计遗留的测试数据与恢复说明

- 当前运行中的 backend 是审计时以 `EMAIL_BACKEND=console` 临时重建的（用于取验证码）；
  本机 `.env` 仍是 `EMAIL_BACKEND=smtp`（凭据失效）。下次 `docker compose up -d`
  会按 `.env` 用 smtp 重建，注册将再次 502，需先修复 SMTP 凭据或改 console。
- 测试数据：两个测试账号、三个客户端（含一个回调被清空的 PhoneScope）、
  A 已绑定手机号 `+8613800000001`。需要清场可删除这两个账号与
  `cli_IZ8y…`/`cli_Cylgx…` 客户端（demo-site 为种子客户端，可保留）。
- 旧栈数据库快照：`backups/pre-fresh-audit-20260816-090212.sql.gz`。
