# 更新日志

## 未发布（开发中）

### 破坏性变更

- **恢复码密钥体系升级（存量恢复码作废）**：移除旧版裸 SHA-256 存储恢复码的兼容校验分支，并把 OTP/恢复码 HMAC 密钥改为从加密主密钥域分离派生（不再与 Fernet 数据加密共用密钥材料）；新迁移 `b7e8f9a0c1d2` 会清空 `recovery_codes` 表。存量恢复码一律失效，用户重新开启 TOTP 即可获得新恢复码；未消费的邮箱/重置验证码随密钥切换失效（10 分钟内自然过期，重新获取即可）。详见 [360° 审查问题修复设计](docs/superpowers/specs/2026-08-16-audit-fixes-round2-design.md)。
- **OIDC token 端点错误格式对齐 RFC 6749**：`POST /oauth2/token` 的错误响应由 `{"detail": "..."}` 改为标准 `{"error": "...", "error_description": "..."}`（HTTP 状态码不变）。此前按 `detail` 字段解析错误的对接方需同步更新（authorize 回跳、userinfo 与 `/oauth2/client/*` 管理接口不受影响）。详见 [对接指南 §3.3/§7](docs/oidc-integration.md)。
- **PKCE 对全部客户端强制**：`/oauth2/token` 不再对机密客户端豁免 `code_verifier` 校验（OAuth 2.1 对齐）。authorize 端点本就要求 `code_challenge`，因此新接入方无影响；已有机密客户端换码时必须携带 `code_verifier`。
- **会话空闲超时配置改名**：`SESSION_IDLE_DAYS`（整数天）→ `SESSION_IDLE_MINUTES`（整数分钟，默认 720，≥5）。旧环境变量不再生效，升级时请把原值换算为分钟写入 `.env`。
- **移除「记住密码」**：登录页不再提供明文密码 localStorage 持久化，仅保留「记住账号」；历史已落盘的 `lipass.remember.password` 会在下次保存时自动清理。需要免密登录请使用浏览器密码管理器；「记住我」的服务端会话 TTL 不受影响。
- **强制二次验证（2FA）**：注册验证邮箱后自动启用「邮箱验证码」作为默认第二方案；所有已验证邮箱的账号登录都必须完成 2FA（新迁移 `a2b3c4d5e6f7` 会把历史「已验证且无任何 2FA」的用户批量启用邮箱验证码）。账号必须至少保留一种 2FA 方案：关闭最后一种会被拒绝；管理端「重置 2FA」不再清空，而是恢复默认邮箱验证码。未验证邮箱的账号仍可密码登录，验证邮箱后立即强制。若邮箱不可达，用户可用 TOTP 或恢复码完成登录；需灰度或回滚时参见 [设计文档](docs/superpowers/specs/2026-08-16-mandatory-2fa-design.md)。
- OIDC `access_token` 的 `aud` 从 `client_id` 改为 `{issuer}/oauth2/userinfo`，并已在 userinfo 端点强制校验。`id_token` 的 `aud` 仍为 `client_id`，不受影响。此前若对接方校验过 `access_token` 的 `aud == client_id`，发布后需同步更新为 userinfo 端点地址。详见 [对接指南 §3.5](docs/oidc-integration.md)。
- 技术标识统一为 `lipass`：Compose 项目/镜像/网络/命名卷由 `account-service` 系列改为 `lipass` 系列，从旧版升级需先按 [部署文档 §标识迁移](docs/deployment.md) 迁移数据卷；`acr` 声明由 `urn:portal-oss:acr:1fa/2fa` 改为 `urn:lipass:acr:1fa/2fa`，接入方在升级期按“两套值等价”校验，窗口过后只保留新值。

### 功能

- 深色模式切换为「D1 雾灰」柔和中间调（背景 `#3A3F45` / 表面 `#434950`，平均亮度约为旧深色的 3 倍，不再压黑），前景/语义色/强调色同步改为雾面低饱和变体；主按钮从多色粉彩渐变改为**半透明单色着色**（浅色 `rgba(47,127,116,.10)`、深色 `rgba(127,212,198,.13)` + 细描边），消除按钮色块过重与页面违和感；签名描边与流光线的深色透明度同步调低，Bento 深色卡改为雾灰卡面，首帧兜底背景（preflight）与浏览器 theme-color 一并对齐。
- 前端视觉再升级（**海玻璃 Sea Glass 配色 + 主界面科技光效**）：按用户指令跳出原有克制框架，全站采用全淡色系——浅水绿主色 `#2F7F74`（深色模式 `#7FD4C6`）、雾面六强调色 `ice/aqua/lilac/sage/mint/sand`（**无粉色、无重色**），按钮/签名描边/流光线统一使用粉彩渐变（`#C9F3E7→#BDE9EC→#C9DFF7→#E4F5E3`）+ 深青文字保证对比；认证页新增科技氛围层 `TechAmbience`（缓移网格、周期性扫掠光束、呼吸光点），用户中心用 `soft` 淡版、管理后台保持克制不加，品牌 Logo 增加海玻璃辉光；深色模式改为柔和的深水绿夜色（`#172321`，不压黑）。全部动效仅动 `transform/opacity/background-position`，`prefers-reduced-motion` 下自动单帧，不触碰后端契约与认证链路。设计见 [UI 色彩与流动光效刷新设计](docs/superpowers/specs/2026-08-17-ui-color-light-design.md)。
- 前端视觉刷新（色彩层次 + 流动光效）：新增六色低饱和强调色板 `cyan/teal/indigo/violet/amber/rose`（明暗双主题各配 strong/soft 令牌）与 `secondary` 令牌，仅用于装饰性小面积——用户中心应用/头像占位瓦片按 ID 稳定哈希配色、分区图标按色相分层、分区标题加流光规则线；管理后台「数据统计」六张概览卡各配色相（标签/图标/光标辉光/迷你图/进度条联动跟随）、认证方式分布条按方式着色、趋势图默认系列色扩展为多色相。流动光效保持克制：主按钮斜向扫光、签名卡片渐变描边缓慢流动、顶栏 1px 流光渐变线、PillTabs 活动标签扫光、用户中心与管理后台新增低浓度极光层；全部仅动 `transform/opacity/background-position`，`prefers-reduced-motion` 下自动降为单帧，不改动任何后端契约与认证链路。设计见 [UI 色彩与流动光效刷新设计](docs/superpowers/specs/2026-08-17-ui-color-light-design.md)。
- 审计日志展示增强：`GET /api/v1/admin/audit-logs` 返回 `category_label`/`action_label` 中文标签与 `actor`（类型标签 + 可读显示名：用户/管理员解析为昵称与邮箱，授权网站解析为站点名，系统显示「系统」；已删除账号回退原始 ID 保留可追溯性）；管理后台审计面板按标签渲染分类/动作徽章，操作者列展示类型徽章 + 可读名称 + 次级原始 ID，动作徽章悬停显示原始动作名。原始英文枚举仍原样返回，不影响历史数据、统计聚合与筛选。
- 更换登录邮箱：用户中心新增「更换登录邮箱」（`POST /api/v1/me/email/change/request|confirm`）——先向新邮箱发送验证码，再凭验证码完成更换；要求每次显式输入当前密码（step-up 窗口不豁免），新邮箱全库唯一并做并发兜底，成功记审计并向旧邮箱发送变更提醒。账号身份不变：OIDC `sub`（用户 UUID）始终是稳定统一标识，`id_token`/`userinfo` 的 `email` 为可变属性，旧令牌最长 15 分钟内自然过期。对接方须按 `sub` 绑定账号（见 [对接指南 §3.4](docs/oidc-integration.md)）。`OtpPurpose` 新增 `change_email`（迁移 `9d2c3b4e5f6a`，PG 枚举只增不删）。设计见 [可变邮箱与 openid 统一账号标识设计](docs/superpowers/specs/2026-08-16-changeable-email-design.md)。
- 活跃对接网站会话感知：`oidc_client_sessions` 链接生命周期闭环——门户会话撤销（用户单会话撤销、退出所有设备、门户登出、管理员单/批量/全部下线）在派发回程登出通知后同步吊销对应链接，重新授权时自动激活已吊销链接；`GET /api/v1/apps` 新增 `active_sessions` 字段，应用广场每张卡片展示「已登录 · N 台设备」或「未登录」，让取消授权/门户登出的下线通知与用户可见状态一致。设计见 [活跃对接网站会话感知设计](docs/superpowers/specs/2026-08-16-active-site-session-awareness-design.md)。
- 邀请注册前置校验：新增 `GET /api/v1/auth/invite/status`（返回脱敏邮箱与是否已注册），邀请页在展示注册表单前先校验链接——无效/已使用/已取消/已过期分别展示对应提示页，邀请邮箱已注册账号时提示直接登录，不再让用户填完信息提交后才报错。
- 登录可信设备（7 天免登录二次验证，**仅登录环节**）：用户完成登录 2FA 时可勾选「信任此设备」，此后 7 天内该设备用正确密码登录跳过 2FA（密码校验不受影响）；豁免不覆盖修改密码/注销/管理端等敏感操作复核。凭证为 256 位随机 token（数据库只存 SHA-256 哈希），Cookie `lipass_trusted_device`（HttpOnly、生产 Secure、SameSite=Lax），有效期可配置 `TRUSTED_DEVICE_TTL_DAYS`（默认 7）；用户中心新增「可信设备」列表与逐台移除，修改密码与「退出所有设备」清除全部可信设备。审计新增 `trusted_device_granted`/`2fa_trusted_skip`/`trusted_device_revoked`。设计见 [可信设备设计](docs/superpowers/specs/2026-08-16-trusted-device-design.md)。
- 注销/删除账号升级为「密码 + 任意 2FA」双因素复核：注销账号、管理端删除用户与批量删除必须同时提供当前密码与一种二次验证码（邮箱验证码或 TOTP），且**不享受 30 分钟免复核窗口**（每次必验）；新增 `POST /api/v1/me/step-up/send` 发送复核邮箱验证码（与登录 2FA 共用发送冷却与每小时配额），前端新增通用双因素复核表单（获取验证码 + 60 秒重发冷却）。设计见 [账号安全与体验改进设计](docs/superpowers/specs/2026-08-16-account-ux-security-improvements-design.md)。
- 密码输入实时强度显示（弱/中/强三段色条）：接入注册、邀请注册、找回密码、用户中心修改密码与管理员代建账号；按长度、大小写、数字、符号评分，仅显示、不改变后端密码策略。
- 注册完成自动跳转登录页并预填邮箱；未验证邮箱的用户登录后仍可在用户中心继续完成验证。
- 登录页新增「记住账号」选项：默认关闭、仅在登录成功后按勾选写入 localStorage，取消勾选即清除。明文「记住密码」已移除（见破坏性变更），请使用浏览器密码管理器。
- 强制 2FA 落地：验证邮箱（普通注册验证、邀请注册、管理员代建）后直接启用邮箱验证码作为默认第一方案；用户可升级到 TOTP 认证器，并可在两种方案并存时关闭其一，但不可清空全部。管理端「重置 2FA」恢复默认邮箱方案并清空 TOTP/恢复码。设计见 [强制二次验证设计](docs/superpowers/specs/2026-08-16-mandatory-2fa-design.md)，实施计划见 [实施计划](docs/superpowers/plans/2026-08-16-mandatory-2fa.md)。
- 敏感操作 step-up 复核窗口：新增 `GET/POST /api/v1/me/step-up`（复核窗口状态与显式密码复核端点）；一次密码复核成功后，该会话在 **30 分钟**内执行其它敏感操作免再次输入密码。窗口为固定时长、按会话隔离（一台设备复核不豁免其它设备）、**登录成功不自动授窗**。用户中心（修改密码/注销账号）、2FA 开关（邮箱验证码/TOTP）与全部管理端敏感操作（角色变更/重置密码/重置 2FA/删除用户/批量删除/删除客户端/重置密钥）统一接入；窗口时长与限流阈值可配置（`STEPUP_WINDOW_MINUTES=0` 可关闭窗口回到每操作必验）。设计见 [敏感操作 step-up 认证窗口设计](docs/superpowers/specs/2026-08-16-sensitive-stepup-window-design.md)，实施计划见 [实施计划](docs/superpowers/plans/2026-08-16-sensitive-stepup-window.md)。
- 联邦登出完整落地：RP 发起登出（`GET /oauth2/end-session` + 确认页 `/logout/confirm` + 精确匹配回跳白名单）、回程登出（`logout_token` 签发/异步分发/重试/SSRF 防护）、无回程网站的浏览器串跳漏斗、用户/管理员会话撤销与取消授权联动下线；`id_token` 新增 `sid`，发现文档新增 `end_session_endpoint`/`backchannel_logout_supported`；管理端新增「登出回跳白名单」「回程登出地址」配置，演示站实现对应 RP 侧示例。详见 [对接指南 §8](docs/oidc-integration.md) 与 [实施计划](docs/superpowers/plans/2026-08-15-federated-logout.md)。

### 安全加固

- 登录 CSRF 补全：`POST /api/v1/auth/2fa/verify`（成功后下发门户会话 Cookie）纳入 Origin 白名单守卫——此前攻击者可用自己的 2FA 挑战与验证码诱导受害者跨站提交，把受害者浏览器登录进攻击者账号（登录串号）；`/api/v1/auth/2fa/send` 与 `/api/v1/auth/email/verify` 一并纳入作纵深防御。非浏览器客户端（无 Origin）行为不变。
- 服务端密码复杂度校验：注册、邀请注册、重置密码、修改密码与管理端代建/重置密码统一要求长度 ≥8 且小写/大写/数字/符号 4 类字符至少 2 类（与前端强度条「中」档一致）；不满足返回 422「密码强度不足」。
- 回程登出地址校验拒绝 IPv4-mapped IPv6（如 `::ffff:127.0.0.1`）：此前此类地址可绕过回环/私网判断，现先还原为 IPv4 再做危险网段校验。
- 生产环境外链头像仅允许 `https`（开发环境仍允许 `http`），与 OAuth 回调地址等 URL 校验口径一致；本地上传头像路径不受影响。
- SMTP TLS 证书校验默认开启（新增 `SMTP_TLS_VERIFY`，默认 `true`）：此前 `SMTP_SSL`/`STARTTLS` 使用 Python 默认的未认证上下文（不校验证书与主机名），中间人可在 SMTP 链路上窃取邮箱账号密码；现默认走系统受信 CA 并校验主机名，仅内网自签证书等场景可显式关闭（关闭时记日志，生产环境为 error 级告警）。
- 注册接口邮箱枚举时序抹平：此前「已注册邮箱」直接返回、跳过 Argon2 哈希（毫秒级），「未注册邮箱」执行哈希（百毫秒级），响应文案一致但耗时可区分账号是否存在；现已注册邮箱同样执行一次同参数哈希，消除该时序侧信道。
- 可信设备 Cookie 清除属性对齐：`lipass_trusted_device` 删除时此前不携带 Secure/SameSite/HttpOnly（与设置时不一致，部分浏览器在 HTTPS 下可能不认可删除），现与设置属性保持一致。
- 管理端代建管理员需密码复核：`POST /api/v1/admin/users` 此前可直接传 `role=admin` 铸造管理员账号，被窃取的管理员会话可借此留下持久后门（绕过「角色变更必须复核」的防护）；现创建管理员与角色变更一致，必须提供 `current_password` 完成 step-up 复核（代建普通用户不受影响）。
- 黑名单接口邮箱格式校验：`ClientBlockCreate.email` 改为 `EmailStr`，畸形邮箱返回 422（此前任意字符串可落库，虽仅做等值比较无实际风险，但会沉淀脏数据）。
- 黑名单接口参数类型收紧：`ClientBlockCreate.user_id` 改为 UUID 类型校验，畸形 `user_id` 返回 422（此前被 `except ValueError` 误捕获为语义错位的 409，错误文案为 UUID 解析异常）。客户端自助接口与管理端接口同步生效。
- OIDC 客户端 scope 收口：`ClientCreate/ClientUpdate` 只接受 `openid/profile/email` 且必须包含 `openid`，与发现文档的 `scopes_supported` 一致，杜绝注册 `phone` 等本 IdP 不会输出的 scope 造成 RP 误解；`ClientUpdate` 同时拒绝把 `redirect_uris`/`scopes` 清成空列表（此前会立刻使客户端不可用）。
- token 端点参数长度上限：`code`（512）、`redirect_uri`（1000）、`client_id`（128）、`client_secret`（256）、`code_verifier`（200）与 authorize 端点对齐，避免直连后端部署形态下超长表单字段造成内存/CPU 放大；PKCE 校验补全 RFC 7636——`code_verifier` 长度窗口 43–128，`code_challenge` 必须为 43–128 字符 base64url。
- 登出确认请求绑定发起会话：`POST /api/v1/oauth/logout-requests/{id}/confirm` 与 `/local-only` 校验待确认请求的 `sid` 与当前门户会话一致，跨会话确认返回 404；`local-only` 不再允许无会话调用，堵住他人会话确认并混用发起者回跳地址/state 的串号路径。
- 头像静态资源缓存契约收紧：后端对 `/uploads/*` 只在 200 时签发 `Cache-Control: public, max-age=604800`，4xx/5xx 一律 `no-store`；网关不再用 `add_header ... always` 覆盖该头，避免把 404/500 缓存 7 天。全新卷上启动时自动创建头像目录，缺失头像文件从 500 修正为 404。
- 管理端手机号绑定唯一性：`POST /api/v1/me/phone/bind` 先查重并捕获唯一约束冲突，重复手机号返回 409（此前未捕获 `IntegrityError` 直接 500）。
- compose 限流默认值修正：`LOGIN_EMAIL_RATE_LIMIT` 编排默认由 20 改为 10，与代码默认值、CHANGELOG「20→10 收紧」及部署文档一致（此前容器部署实际生效 20，比文档宣称宽松一倍）。
- 登录账号枚举时序抹平：邮箱不存在时同样执行一次同参数 Argon2 校验，消除「无此账号」与「密码错误」的响应耗时差异。
- 登录/注册跨站校验：`POST /api/v1/auth/login` 与 `/register` 在携带 Origin 且不在 `CORS_ORIGINS` 白名单时返回 403，阻断登录 CSRF 与跨站注册滥用（缺失 Origin 的 curl 等非浏览器客户端不受影响）。
- 密码/2FA 重置统一吊销可信设备：自我重置密码、管理员重置密码与管理员重置 2FA 三条路径与「修改密码/退出所有设备」一致，全部调用 `revoke_all_trusted_devices` 并记 `trusted_device_revoked` 审计，堵住「重置后旧可信设备仍免 2FA」的旁路。
- 恢复码熵 64 bit → 128 bit（`token_hex(16)`），HMAC 落库方式不变。
- OIDC 合规加固：token 端点错误对齐 RFC 6749；`id_token` 新增 `at_hash`（token 端点同时返回 access_token 时的 OIDC 必填项）；`nonce` 为空时不再输出 `null`；authorize 参数（nonce/state/code_challenge/redirect_uri/client_id/scope）增加长度上限，杜绝 PostgreSQL VARCHAR 超长导致 500；发现文档补齐 `token_endpoint_auth_methods_supported` 与 `claims_supported`。
- `/oauth2/authorize` 与 `/oauth2/token` 增加按 IP 限流（`AUTHORIZE_RATE_LIMIT`/`TOKEN_RATE_LIMIT`，默认 120/分钟），token 超限按 `{"error":"rate_limited"}` 返回。
- 授权请求绑定发起用户：`PendingAuthRequest` 记录 `user_id`，同意/拒绝校验与当前会话用户一致，防止多账号场景下的串号授权。
- 回调地址拼接修复：redirect_uri 已含查询串时用 `&` 追加 `code`/`error`/`state`，修复 `?foo=bar?code=...` 导致的 RP 解析失败。
- 回程登出 DNS 固定：生产环境把安全校验解析出的公网 IP 列表固定到连接层（httpcore 自定义 backend，SNI/证书校验仍用原域名），消除「校验解析」与「实际连接」间的 DNS rebinding 窗口；回程地址拒绝 `#` 片段。
- 后端 CSP 追加 `object-src 'none'`、`base-uri 'self'`、`form-action 'self'`、`frame-ancestors 'none'`。
- 会话守护补全：新增 `GET /api/v1/me/session` 与 `/me` 内的会话生命周期字段；新增 `POST /api/v1/auth/logout/local`（仅吊销当前门户会话，不派发回程登出、不串跳，供授权确认页切换账号）；前端 API 客户端对会话保护端点的 401 派发 `lipass:unauthorized` 事件并带 `next` 跳登录；前端按会话空闲倒计时做 5 分钟提示与到期兜底。
- 前端生产 CSP 修复与收紧：主题初始化脚本与兜底样式由内联改为外链（`theme-init.js`/`preflight.css`），生产 CSP 明确 `script-src 'self'`；`img-src` 放行 `https:` 以加载授权应用 logo（配合 `Referrer-Policy: no-referrer`）。
- 回程登出地址校验加固：拒绝携带用户名/密码的 URL；生产环境除强制 https 外，进一步限定只能使用 443 端口；域名经 IDNA 规范化后再做公网解析校验（防回环/私网/链路本地绕过）。管理员创建/修改授权网站时立即校验「回程登出地址」，非法地址当场返回 400，不再等到登出分发时才跳过。
- 登录兜底强制 2FA：对「已验证邮箱却没有任何 2FA 方案」的历史账号（迁移遗漏、异常数据），登录时自动启用邮箱验证码并记审计 `2fa_email_auto_enabled`，保证「至少一种 2FA」不变式不被绕过。
- 敏感操作的密码复核统一收敛到 `app/services/stepup.py`：此前散落各路由的 `current_password` 校验无独立限流，现新增按邮箱+IP 与全局邮箱的双层复核失败限流（默认 5/10 次每 15 分钟），并落 `stepup_verify_success`/`stepup_failed`/`stepup_required` 审计（category=`security`），复核被拒与疑似会话窃取的免密尝试可追踪。
- 依赖安全审计（pip-audit）：`python-multipart 0.0.20 → 0.0.32`（修复多个 2026 年公告的 multipart 解析 DoS）、`pyotp 2.1.0 → 2.10.0`（移除其携带的有漏洞传递依赖 `future 0.15.2`）；升级后 pip-audit 清零，npm 生产依赖审计 0 漏洞。
- 后端镜像的 ip2region 数据与 Python 绑定源码改为构建时从固定 tag 拉取（SHA256 信任清单校验、下载带重试），修复镜像遗漏 vendored 绑定源码导致容器启动 `ModuleNotFoundError: No module named 'ip2region'`；构建期新增 `import app.main` 冒烟检查，把此类“漏 COPY/漏拉取”问题前移到镜像构建阶段暴露。构建下载基地址可用 `IP2REGION_DOWNLOAD_BASE_URL` 覆盖（Gitee raw 实测拒绝 xdb 数据文件，需保持 GitHub 源）。
- 依赖安全升级：`fastapi 0.115.6 → 0.141.1`、`starlette 0.41.3 → 1.6.0`（修复 CVE-2026-48710「BadHost」Host 头认证绕过、CVE-2025-62727 Range 头 DoS、CVE-2025-54121 multipart 主线程阻塞）、`cryptography 44.0.0 → 50.0.0`（修复内嵌 OpenSSL 公告与 PKCS7 Bleichenbacher oracle）、`PyJWT 2.10.1 → 2.13.0`（修复 CVE-2026-32597 crit 头未校验）；新增 [Dependabot](.github/dependabot.yml) 每周依赖漏洞扫描。
- ip2region 运行期更新强制 SHA256 信任清单：仅清单内版本可安装（`app/services/ip2region_pins.py`），未知版本/哈希不符一律拒绝并保留旧库；构建期脚本与运行期共用同一清单。
- ip2region 更新互斥改为数据目录上的跨进程文件锁（fcntl），修复多 worker 并发写同一临时目录的竞态；双文件替换改为先备份再原子替换、任一失败自动回滚，杜绝 v4/v6 版本错位。
- 损坏/错位的 xdb 数据不再击穿管理端接口：加载期校验结构版本与 IP 版本，查询期兜底降级为「未知」，不再抛未捕获异常导致 500。
- IP 库手动更新失败不再向客户端泄露内部异常细节：并发冲突返回 409，其余失败记日志并返回固定文案。
- 运行期更新的 IP 库数据持久化到新命名卷 `backend-data`（`/app/data`），容器重建后保留，避免反复重下。
- 管理后台数据统计：审计日志新增 `(action, created_at)` 复合索引（新迁移 `6d1f9c0b2e4a`），聚合快照增加 60 秒进程内缓存；「系统信息」「数据统计」查看动作补审计记录。
- 自动更新间隔防御性钳制（脏数据 0/负值不再退化为每小时更新）；站点设置 PUT 改为可选字段（PATCH 语义），修复两个管理员并发保存互相覆盖公开注册开关的问题。

### 行为变更

- 弱口令注册/设置密码会被服务端直接拒绝（422），不再仅靠前端强度提示；`GET /oauth2/userinfo` 的 401 响应新增 `WWW-Authenticate: Bearer realm="userinfo"`（RFC 6750）。
- 管理端代建管理员（`POST /api/v1/admin/users` 且 `role=admin`）必须携带 `current_password`：旧调用方（脚本/自动化）创建管理员时未携带该字段将收到 403「需要重新验证密码」，需同步更新；代建普通用户与邀请注册不受影响。
- 邮件发送失败统一返回 `503 Service Unavailable`（此前为语义错误的 `502 Bad Gateway`，会污染网关/监控的 502 指标）；覆盖注册、重发验证码、2FA 发码、step-up 发码、手机绑定发码、找回密码与管理端邀请。
- 授权确认页新增「正在以 xxx 登录」身份展示与「使用其他账号登录」（本地登出后带 `next` 回到原授权流程）。
- 站内信铃铛在窗口重新可见/聚焦时刷新未读数；登录页邮箱输入 `autoComplete="username"`；弹窗新增 Tab 焦点陷阱。
- 用户中心与管理后台接入会话空闲提醒：剩余 5 分钟提示一次，倒计时归零自动跳转登录（`next` 保留）。
- 门户「退出登录」纳入二次确认：点击后弹出确认框（撤销当前门户会话并登出所有已授权网站），确认即退出；确认环节**不要求重新认证**（不输入密码/验证码）。
- 应用广场取消授权反馈更准确：撤销响应新增 `backchannel_configured`，前端据此区分三种结果——已派发回程通知 / 配置了回程登出但未找到活跃登录关系 / 未配置回程登出，不再把「未找到登录关系」误报成「未配置回程登出」；撤销后应用列表改为重新拉取服务端数据。
- 用户中心（应用广场/登录设备/可信设备）每次进入页面自动刷新一次：除首次挂载外，切回标签页或窗口重新可见时自动重新拉取列表（防抖 500ms），无需手动刷新。
- 已验证邮箱账号的登录 2FA 界面新增「信任此设备：7 天内登录免二次验证」复选框（默认不勾选）：勾选后该设备 7 天内登录免 2FA，豁免仅限登录环节；未勾选行为不变。修改密码或「退出所有设备」会清除全部可信设备。
- 应用广场取消授权与登出联动补强：撤销授权时同步吊销该用户在此客户端上的门户会话链接（保持状态一致，并避免后续门户登出继续向已取消授权的网站派发回程通知）；撤销响应新增 `backchannel_notified` 标记。**取消授权不再跳转到目标网站**——网站下线只通过服务端回程登出通知，浏览器始终停留在门户；未配置回程地址的网站会明确提示用户在该网站手动退出（退出门户的浏览器串跳不受影响）。
- 对接规范明确化：`docs/oidc-integration.md` 新增「§2 对接方接口契约（必选/可选）」与接入验收清单——授权回调接口为必选（校验 `state`、`error` 按失败处理、完整校验 `id_token`、本地会话绑定 `(sub, sid)`）；登出通道（回程登出 / 登出地址）至少二选一；登出回跳页在使用 RP 发起登出时必填。注册客户端表单字段与接口的必填/选填关系同步成表，原有章节顺延编号。
- 登录页与验证邮箱页对「返回原网站的链接（`next`）」校验失败不再静默：当 `next` 的域名/协议与门户当前访问源不一致（典型如 `PUBLIC_BASE_URL` 误配为 `http://` 而实际以 `https://` 访问）时，页面展示明确告警并说明登录/验证后将停留在门户个人中心，避免用户在不知情下丢回调。部署文档同步强调 `PUBLIC_BASE_URL` 必须与浏览器实际访问的完整源（含协议）一致。
- 登出语义明确化：`end-session` 确认页把含糊的「确认退出 / 取消」改为两个明确选项——「登出 SSO」（吊销门户会话并通知全部授权网站）与「仅登出本网站」（保留门户会话、仅回跳；发起网站的本地会话由该网站在跳转前自行结束）。内部确认端点 `POST /api/v1/oauth/logout-requests/{id}/cancel` 重命名为 `/local-only`（仅本项目前端调用，无外部接入方影响）；演示站登录后拆出「登出本网站」「登出 SSO（退出所有网站）」两个按钮。对接指南 §8 新增「两种登出语义」小节。
- 注销账号、删除用户、批量删除由「密码复核 + 30 分钟窗口豁免」收紧为「密码 + 任意 2FA 每次必验」：旧客户端缺少 `stepup_method`/`stepup_code` 将收到 400，需同步更新前端。
- 敏感操作在「未提供当前密码且不在复核窗口内」时返回 **403「需要重新验证密码」**（原为 422 或 400）；密码错误仍返回 400「当前密码错误」。旧前端始终携带密码，行为不受影响；前端接入复核窗口后可在 30 分钟内免密码执行后续敏感操作。
- 管理后台面板级代码分割：8 个标签面板改为懒加载（React.lazy + Suspense），访问任一标签不再下载全部面板代码，后台入口分包由约 661KB 降至约 8.5KB；数据统计的地图 GeoJSON（约 578KB）改为组件挂载时按需异步加载，坐标精度收敛到 3 位小数（约 425KB，gzip 约 121KB），构建不再出现超大分包警告。
- 管理后台「数据统计」概览卡片改为 React Bits MagicBento 风格的深色 Bento 网格（新组件 `MagicBento`）：支持光标跟随聚光、悬停粒子星点、边框辉光、3D 倾斜与磁性吸附，光色默认跟随明暗主题的品牌主色（可用 `glowColor` 覆盖为 RGB 三元组）；统计页启用 `compact` 紧凑模式（等宽 3 列、单卡高 144px），卡片带分类图标与副标题，账号/邮箱卡附占比进度条，登录与注册卡附迷你趋势线，并按卡片用途可点击跳转对应管理标签（用户/会话/审计）；移动端与 `prefers-reduced-motion` 下自动关闭动画、仅保留静态卡片。
- 管理后台顶部标签由按钮组改为 React Bits PillNav 风格的胶囊标签（新组件 `PillTabs`）：hover / 键盘聚焦时主色圆环自胶囊底部中心展开、旧文案上滑、主色前景文案从下方滑入，活动标签固定为主色胶囊；保留原 `ScrollTabs` 的横向滑动、边缘渐隐与深链居中能力，渐隐起始色新增 `fadeColor` 参数以贴合轨道背景，`prefers-reduced-motion` 下动画瞬切。
- 认证页与用户中心接入 React Bits 风格的 `StrokeText` 描边绘制标题（gsap 依赖）：页面标题按字符描边后从左向右擦入填充，描边/填充色走 `--portal-primary`/`--portal-fg` 令牌自动跟随明暗主题，`prefers-reduced-motion` 下直接呈现最终态；`ScrollTrigger` 仅在 `trigger="scroll"` 时按需加载。视觉层同步微调：极光背景色相加入青/紫低透明度点缀、认证卡新增蓝→青→紫渐变描边（`.card-signature`）、主按钮改为「主色→主色悬停」纵向渐变并在 hover 时下移渐变与抬升阴影，浅深主题分别调色。
- 品牌名统一为 **Li&Pass**：前端品牌配置、页面标题/文案、邮件主题与模板、TOTP issuer、User-Agent、Compose/环境变量示例与全部文档同步更新。
- 会话 Cookie 由 `portal_session` 改为 `lipass_session`：后端同时接受两个名字（旧浏览器中的会话自然过期前仍可登录），新会话签发新名，登出同时删除两个名字。JWT 单文件模式 kid 由 `portal-rs256-1` 改为 `lipass-rs256-1`：JWKS 同时发布新旧两个 kid 指向同一公钥，旧 kid 令牌到期前仍可验证，新签名一律用新 kid；轮换脚本兼容历史 `portal-rs256-*.pem` 编号。
- 用户中心「登录设备」新增「退出所有设备」：一键下线除当前会话外的全部设备。后端新增 `POST /api/v1/sessions/revoke-all`（先清理本用户过期/空闲的僵尸会话、再撤销其余会话、保留当前会话并记录审计），前端新增危险按钮与确认弹窗，完成后刷新列表并提示退出设备数；仅剩当前设备时按钮禁用。
- 管理后台标签栏改为全局横向滑动策略：新增通用 `ScrollTabs` 组件，标签单行排列、超出宽度时左右滑动而非换行堆叠（隐藏滚动条、snap 轻吸附、阻止滚动连带页面滚动），可滚动方向叠加主题色边缘渐隐提示，挂载与切换标签时活动标签自动滚入视口中央（深链直达 `/admin/audit` 等活动标签始终可见）；移动端通栏呈现，并统一激活/非激活标签高度，消除激活态 2px 高低错位。
- 数据统计「登录来源地域分布」由 Top 10 条形列表改为中国地图省级着色：后端新增 `regions_map`（省级聚合，含内蒙古/港澳等别名规范化）与 `regions_other`（海外/内网/未知汇总），前端新增自研 SVG `ChinaMap` 组件（GeoJSON 入库离线、5 档单色渐变与色阶图例、悬停省份提示次数与占比、海外/内网/其它徽章与明细表兜底）。设计见 [登录来源地域分布地图设计](docs/superpowers/specs/2026-08-15-admin-login-region-map-design.md)。
- 设备管理支持详细型号：后端响应新增 `Accept-CH: Sec-CH-UA-Model, Sec-CH-UA-Platform-Version`，Chromium 系浏览器登录时会话记录具体型号（如「MacBook Pro · macOS 14.5」）；Safari/Firefox 等不提供型号时降级为 UA 解析（如「iPhone · iOS 17.5 · Safari」「Android 14 · Chrome」）。历史会话存储的原始 UA 在读取时自动解析为友好设备名，用户中心与管理后台同步生效。
- 构建提速：后端与演示站镜像的 `apt-get update` 新增 `APT_MIRROR` 构建参数（默认中科大镜像 `http://mirrors.ustc.edu.cn/debian`，同时覆盖 debian-security），修复基础镜像直连 deb.debian.org 导致的慢更新；海外构建可改回官方源。实测 10.1MB 索引/包 7–8 秒拉完。
- 应用广场改为单列行布局：每个网站占一整行，左侧 logo/名称/描述（横置单行截断），「进入」「取消授权」按钮贴最右；窄屏自动换行仍右对齐。全局 `.btn`/`.btn-link` 禁止文字换行，避免按钮文案异常折行。
- 站点设置「IP 归属地库」的「立即检查更新」改为后台任务 + 实时进度：`POST /settings/ip2region/update` 立即返回 202，下载在服务端后台继续（独立 DB 会话），新增 `GET /settings/ip2region/update/status` 上报阶段（检查/下载 IPv4/下载 IPv6/安装）与字节级百分比；前端每秒轮询并显示进度条，离开页面不中断、回来可恢复，完成/失败均有提示。设计见 [IP 库后台更新与实时进度设计](docs/superpowers/specs/2026-08-14-admin-ip2region-update-progress-design.md)。
- ip2region 数据与 Python 绑定源码改为随仓库跟踪入库（`backend/data/ip2region/` 与 `backend/ip2region/`，v3.17.0，SHA256 与信任清单一致），镜像构建直接 COPY、不再联网下载，解决远端拉取过慢问题；移除 `IP2REGION_DOWNLOAD_BASE_URL` 构建参数（运行期更新仍使用该环境变量）。更新数据/绑定时先运行 `python scripts/download_ip2region.py --data-dir data/ip2region --binding-dir ip2region` 再提交。
- 桌面端留白优化：已登录页面统一放宽内容区宽度——管理后台、用户中心、收件箱由 `max-w-5xl/4xl/3xl` 统一为 `max-w-7xl`（1280px），顶栏/骨架屏/页脚同步，并新增 `lg:px-8` 大屏内边距；登录/注册/授权确认等表单页保持窄版（`max-w-md`）不变。
- 管理后台「用户管理」新增「刷新」按钮：按当前搜索词与筛选条件重新拉取用户列表，加载中禁用、成功/失败均有提示，与会话监控等其他管理面板保持一致。设计见 [用户管理刷新按钮设计](docs/superpowers/specs/2026-08-14-admin-users-refresh-button-design.md)。
- pip 源切换为中科大镜像 `https://mirrors.ustc.edu.cn/pypi/simple`：后端与演示站镜像构建通过 `PIP_INDEX_URL` 构建参数使用（海外构建可改回官方源），本地开发步骤同步更新；CI 保持官方 PyPI（GitHub 托管 runner 在海外走镜像更慢）。
- 前端镜像构建优化：构建基础镜像 `node:20-alpine → node:22-alpine`（消除 jsdom 依赖链的引擎不匹配警告，与 CI 对齐），`npm ci` 启用 BuildKit 缓存挂载并跳过 audit/fund 网络往返，重建提速；`package.json` 显式声明 `engines.node >=22.14.0`。

### 缺陷修复

- 并发注册同一邮箱不再出现 500：`POST /api/v1/auth/register` 捕获并发撞邮箱触发的唯一约束冲突，回滚后与「已注册」路径返回相同受理文案（含同参数 Argon2 哈希以维持时序抹平）。
- 用户侧会话列表与「应用广场 · 已登录设备数」按空闲超时口径过滤：与管理端在线会话统计一致，空闲超时但未触发吊销的会话不再显示为在线（`GET /api/v1/sessions`、`GET /api/v1/apps` 的 `active_sessions`）。
- 演示站登出漏斗修复：`/demo/logout` 现接受与门户同源的绝对 `next` 地址，门户发起的浏览器串跳不再断链；非同源绝对地址仍回退自身首页（无开放重定向）。
- 已登录用户访问 `/login?next=<绝对同源地址>` 时改用浏览器导航恢复授权/跳转，不再因 React Router 内部解析落到首页；注册成功提示文案与后端语义对齐（「已受理，请查收验证邮件」）。
- 管理后台统计口径修正：「在线会话」与「在线会话认证方式分布」此前只按 `expires_at` 判断，把空闲超时但尚未过期的会话也计入在线；现同时要求 `last_used_at` 在 `SESSION_IDLE_MINUTES` 窗口内，与用户中心/会话监控的在线口径一致。
- 前端镜像在全新检出/干净构建上下文下构建失败：`src/lib/brand.ts` 为本地配置文件未入库（示例为 `brand.example.ts`），缺少该文件时 `tsc` 报 `Cannot find module '../lib/brand'`，`npm run build` 以退出码 2 中止。现 Dockerfile 在构建前检查，文件缺失时用 `brand.example.ts` 兜底复制；构建上下文中已放置自定义 `brand.ts` 时优先保留，与 CI 的复制步骤行为一致。
- 访客无法打开注册/找回密码/重置密码页：全局 401 兜底会把 `GuestOnly` 的会话探测（`/api/v1/me`）误判为会话失效并跳回登录页，导致从登录页点击「注册新账号」「忘记密码？」后立即被弹回（`/login?next=…`）。现 `GuestOnly` 改用静默探针（`authApi.meSilent`，401 不派发全局跳转事件），访客正常到达目标页；真实会话过期场景的兜底跳转不受影响。
- 修复头像首次访问 500、重复绑定手机 500、跨会话确认登出、scope/回调地址校验等缺陷，详见「安全加固」新增条目。
- 邀请注册的账号被删除后无法再次邀请：删除账号时把「已消费邀请还原为待注册」的逻辑会让该邀请继续被视为「已邀请」，管理员再次对该邮箱发邀请被 `该邮箱已收到邀请，请勿重复发送` 拦住（要等 7 天过期或手动删除）。现改为删除账号时将已消费邀请标记为「已取消」——旧链接立即失效（`invite/register` 返回无效），历史记录不再阻塞重新邀请，管理员可立即发出全新邀请；管理端列表该记录显示「已取消」。
- 门户退出登录的登出覆盖补全：此前只对「当前门户会话」的授权链接派发回程通知，且浏览器串跳会排除已配置回程地址的网站——门户会话轮换后，旧会话授权过的网站收不到通知；浏览器 Cookie 型网站即使配了回程地址也不会被串跳清掉会话。现门户登出按用户收集全部未撤销授权链接（跨会话）派发 `logout_token`，串跳漏斗覆盖所有配置了 `logout_uri` 的网站（与回程并存互不替代），保证「撤销当前会话、登出所有授权」。
- 取消授权时回程登出通知此前只覆盖「门户会话仍活跃」的链接：若用户此前已退出门户或门户会话被撤销，即使网站配置了回程登出地址，`backchannel_notified` 仍为 false，前端误报「该网站未配置回程登出」。现取消授权按「用户 × 客户端」收集全部未撤销链接（不再过滤门户会话是否结束），RP 本地会话仍存活时也能收到 `logout_token` 下线。
- 验证码成功消费不再计入限流：`POST /api/v1/auth/2fa/verify` 与 `POST /api/v1/auth/email/verify` 此前无论成败都累计 `twofa_verify`（按 IP）/`email_verify`（按邮箱）计数，同一来源在窗口内连续成功验证会被误判 429；现成功即撤销本次计数，仅失败尝试累积限流，与 step-up 复核「成功即重置」的既有语义对齐。
- OIDC 授权请求带 `email` scope 且用户邮箱未验证时，跳转验证邮箱页会丢失原授权请求：验证完成后用户停留在验证页，只能手动「去登录」，无法自动跳回应用。现后端在跳转中附带 `next`（编码后的原授权请求），验证成功后前端自动回到授权流程并按常规链路跳回 `redirect_uri`；同时登录页「注册新账号」与注册页跳转登录页也透传 `next`，注册新账号后同样能回到应用。
- 设备信息解析误把 Chromium Client Hints 的 GREASE token 当作浏览器名：新版 Chrome 的 `sec-ch-ua` 使用 `Not=A?Brand` 变体，旧黑名单只覆盖 `Not A;Brand`/`Not)A;Brand`/`Not_A Brand`，导致设备管理与会话监控显示「macOS · Not=A?Brand」。现改为按 GREASE token 的结构匹配（`Not?A?Brand`，中间为非字母数字字符）过滤；读取侧对历史已写入的脏名称优先按原始 UA 重建，无 UA 时剔除 GREASE 片段，用户中心与管理后台同步修复。
- 网关演示站动态上游解析的 `proxy_pass` 带变量时其 URI 部分会整体替换原始路径，`/demo/login`、`POST /demo/logout` 等子路径被透传成 `/`（404/405）；已改用 `rewrite` 显式剥离 `/demo` 前缀后不带 URI 转发。
- 联邦登出迁移 `7f2a9d3c8e1b` 的 downgrade 在 PostgreSQL 上失败：`authorization_codes.session_id` 外键未命名导致无法生成 `DROP CONSTRAINT`；已命名外键并在真实 PostgreSQL 上验证 downgrade/upgrade 往返。
- 头像上传超限修复：`starlette 1.6.0` 已将 `HTTP_413_CONTENT_TOO_LARGE` 更名为 `HTTP_413_REQUEST_ENTITY_TOO_LARGE`，超限头像此前会在校验时抛出 `AttributeError`（表现为 500 而非 413），已改用新常量并保留现有测试覆盖。
- 地域分布地图口径修正：IP 库内未识别记录（country 为空，如 `0|0|0|0|0`）此前被误计入「海外」，现归「未知」；无省份数据（仅海外/内网/未知）时不再渲染无意义的色阶图例；悬停提示框左边界钳制，避免极窄视口越界。
- 测试环境异常修复（此前"升级依赖后首跑大量失败"的真实根因）：`Settings` 的 `.env` 原为相对当前工作目录解析，从仓库根运行测试时会误加载根目录的部署 `.env`（`ALLOWED_HOSTS` 不含 testserver、`EMAIL_BACKEND=smtp` 等），导致约 180 个测试批量 400。现改为固定相对 `config.py` 解析为 `backend/.env`，与工作目录解耦；并新增根目录 `pytest.ini`（`testpaths=backend/tests` + `pythonpath=backend`），支持从仓库根直接运行全量测试。
- 页脚不再展示占位假备案号：`ICP_FILING_TEXT`/`POLICE_FILING_TEXT` 默认留空，未配置时隐藏备案链接，填入真实备案信息后自动显示（上线前清单同步提醒）。
- 折线图图例在窄屏禁止换行后改为容器内横向滚动，避免溢出页面产生横向滚动条；Client Hints 品牌解析兼容 `Not)A;Brand`（品牌名含分号，改为引号感知正则）。
- 数据统计的 60 秒快照缓存导致用户禁用/删除/注册后立即查看仍显示旧数据：在用户创建、状态/角色变更、批量更新与账号删除等写路径上主动失效统计缓存（`invalidate_admin_stats_cache`），禁用用户后统计立即反映。
- 数据统计折线图图例与悬停提示文字禁止异常换行（`whitespace-nowrap`），图例不再折行。

### 运维工具

- 开发环境已知行为：`PENDING_REQUEST_STORE/TWOFA_STORE/RATE_LIMITER=memory` 依赖单 worker 进程内状态，且 uvicorn `--limit-max-requests 10000` 会在重启 worker 时清空限流计数与进行中的 2FA 挑战；生产环境配置校验已强制使用 redis 并建议多 worker 时同步放大连接池（见 [部署文档 §环境变量](docs/deployment.md)）。
- 编排文件与前端环境变量文件示例化：仓库改为提交 `docker-compose.example.yaml`（复制为 `docker-compose.yaml` 使用，本机版已 gitignore、可按环境就地修改）；`frontend/.env.example` 改为注释模板（同源网关留空 / 直连后端两种用法示例）；备份/恢复脚本在未复制编排文件时自动回退到 example；README/AGENTS/部署文档同步补充 `cp` 步骤。品牌/站点信息（应用名、备案文案、页脚链接）同时环境变量化：`brand.example.ts`（复制为 `brand.ts` 使用，后者已 gitignore）优先读 `VITE_APP_NAME`/`VITE_APP_TAGLINE`/`VITE_ICP_FILING_*`/`VITE_POLICE_FILING_*`/`VITE_FOOTER_LINKS`，未设置回退内置默认值；前端 Dockerfile 与 compose 增加同名 build args，示例文件补充全部可选项；CI 前端任务增加「复制 brand.example.ts」步骤。
- 补齐网关 `nginx:1.27-alpine` 的 `IMAGE_REGISTRY` 前缀：现在编排内全部镜像（PostgreSQL/Redis/nginx 与三个自建服务，以及三个 Dockerfile 的基础镜像）都可用同一个镜像站前缀统一替换加速。
- 备份脚本输出文件名前缀由 `portal-` 统一为 `lipass-`（脚本依赖 Compose 服务名，随项目改名无需其它改动）。
- 补齐身份降级脚本 `scripts/demote_admin.py`：`python -m scripts.demote_admin <邮箱>` 把管理员降级为普通用户（已是普通用户则幂等跳过；拒绝降级最后一名管理员，防止失去后台入口），与 `make_admin` 对称。
- 前端 npm 源切换为国内镜像 `registry.npmmirror.com`（项目级 `.npmrc`，Docker 构建与本地安装均生效；USTC 的 npm 镜像已停服并重定向至该源）。
- 登录防爆破阈值收紧（默认值变更）：每邮箱+IP 失败次数 `LOGIN_RATE_LIMIT` 10→5（第 6 次密码错误返回 429）、全局限邮箱 `LOGIN_EMAIL_RATE_LIMIT` 20→10、每 IP `LOGIN_IP_RATE_LIMIT` 30→20。注意邮箱级限流的短时账号锁定权衡：攻击者可用错误密码暂时锁住目标账号，见 [部署与运维 §环境变量](docs/deployment.md)。
- HSTS：由部署环境的外层网关统一配置（`Strict-Transport-Security: max-age=63072000; includeSubDomains`）；编排内网关不签发，后端在生产（`SESSION_COOKIE_SECURE=true`）以相同值兜底签发 API 响应。
- 修复：移除编排内网关的 HSTS `if` 块（nginx 不允许在 server 级 `if` 内使用 `add_header`，曾导致 gateway 容器 `[emerg]` 启动失败）。
- CORS 收紧：`allow_methods` / `allow_headers` 由通配改为显式白名单，带凭据的跨域请求不再反射任意请求头。
- CSP 收紧：后端生产环境 `style-src` 移除 `'unsafe-inline'`；前端 CSP 改为 `style-src 'self'; style-src-attr 'unsafe-inline'`（阻断 `<style>` 元素注入，动态进度条/动画依赖的 style 属性不受影响）。
- 部署文档补充：外部 nginx 终止 TLS 的参考配置（`ssl_ecdh_curve X25519:prime256v1:secp384r1` 优先 X25519、TLS 1.2/1.3、OCSP 装订）与 Let's Encrypt 90 天证书的自动续期、到期监控说明。
- `/oauth2/authorize` 请求含 `email` scope 时，服务端强制校验邮箱已验证；未验证用户被 302 到验证邮箱页，验证后需重新发起授权（原授权上下文不保留，见 [统一登录门户设计 §4.4](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)）。
- `userinfo` 与 `id_token` 在 `profile` scope 下新增 `picture` claim（头像绝对 URL）。
- 审计日志与已吊销/已过期会话增加保留期自动清理（`AUDIT_RETENTION_DAYS` 默认 180 天、`SESSION_RETENTION_DAYS` 默认 30 天）。
- 新增可选的 JWT 签名密钥轮换（目录模式多 kid），未配置 `JWT_KEYS_DIR` 时行为不变。
- SMTP 邮件发送增加超时、瞬时失败重试与批量邀请单连接发送。
- 前端体验与可访问性：管理后台五个标签改为可直接访问的子路由（`/admin/*`）；全部密码框支持显示/隐藏切换；「当前密码」类校验失败改为字段旁内联提示；深色模式危险按钮文字对比度修正至 WCAG AA。
- 管理后台新增「系统信息」标签页：展示宿主机与进程的内存占用、磁盘使用、CPU 负载均值、运行时长、运行环境以及数据库/Redis 服务状态，支持手动刷新；指标采集依赖 `psutil`，仅管理员可访问。
- 管理后台新增「数据统计」标签页：实时聚合账号总量与构成（启用/禁用/管理员/已验证邮箱）、最近 7/30/90 天的每日登录次数、登录人数（去重）与新增注册趋势（自研 SVG 折线图，含图例与悬停提示），以及在线会话认证方式分布；数据来自现有用户/会话/审计表，不新增存储。设计见 [管理后台数据统计设计](docs/superpowers/specs/2026-08-14-admin-stats-design.md)。
- 管理后台新增 IP 归属地能力：会话监控与审计日志在 IP 旁展示归属地（中国显示省份+城市、海外显示国家、内网/保留地址单独标注）；数据统计新增「登录来源地域分布」Top 10；站点设置新增「IP 归属地库」卡片，支持查看版本与加载状态、「立即检查更新」手动更新与可开关的定期自动更新（下载→校验→原子替换，失败保留旧库）。数据源为离线 ip2region v3.17.0（Apache-2.0），查询不依赖外网。设计见 [IP 归属地展示、统计与库更新设计](docs/superpowers/specs/2026-08-14-admin-ip-region-design.md)，部署说明见 [部署与运维 §IP 归属地库](docs/deployment.md)。
- 管理后台会话监控新增「批量下线」与「全部下线」：表格支持勾选多个会话批量强制下线；全部下线只作用于除当前会话之外的全部在线会话，当前会话始终受到保护；批量/全部下线按管理员限流（默认 30 次/分钟）。安全审查结论见 [会话监控批量下线设计 §6](docs/superpowers/specs/2026-08-14-session-batch-revoke-design.md)。
- 新增站内信与自定义邮件通知：管理后台「通知管理」可向全部用户或在已注册用户列表中勾选发送站内信与邮件（正文支持 `{nickname}`、`{email}` 占位符）；用户中心新增收件箱与头部未读铃铛，并可在资料中关闭邮件通知。设计见 [站内信与自定义邮件通知设计](docs/superpowers/specs/2026-08-14-notifications-design.md)。
- 站内信支持撤回：管理员可在发送历史中撤回已发的站内信，撤回后收件人收件箱不再显示该消息（已发出的邮件无法撤回）。
- 邮件通知升级为品牌风 HTML 模板：验证码、重置密码、邀请、账号删除与自定义通知五类邮件统一使用品牌 Logo（CID 内嵌、不依赖外网）、安全蓝按钮/验证码底色块与 Z 形品牌暗线，支持深色模式自适应；同时保留纯文本降级（`multipart/alternative`）以保障送达率。
- 新增 BIMI 发件人头像：内置从品牌 Logo 提取的 SVG Tiny P/S 矢量文件（`/bimi/logo.svg`），配合 DMARC 强制策略与 `default._bimi` DNS 记录即可在邮箱客户端展示品牌头像；配置说明见 [部署指南 §BIMI](docs/deployment.md)。
- 邀请注册的账号被删除后，其已消费的邀请记录会还原为「待注册」而非残留「已使用」，同一邀请链接可在有效期内再次完成注册。
- 前端品牌氛围「环境呼吸感」：新增纯 Canvas 循环飘动背景（Z 形 / 正方形 / 平行四边形），认证页含输入聚焦减速、用户中心含滚动风速联动、管理后台极致克制；移动端自动减量，全部尊重 `prefers-reduced-motion`。设计见 [循环飘动氛围层设计](docs/superpowers/specs/2026-08-14-ambient-background-design.md)。
