# 更新日志

## 未发布（开发中）

### 破坏性变更

- **强制二次验证（2FA）**：注册验证邮箱后自动启用「邮箱验证码」作为默认第二方案；所有已验证邮箱的账号登录都必须完成 2FA（新迁移 `a2b3c4d5e6f7` 会把历史「已验证且无任何 2FA」的用户批量启用邮箱验证码）。账号必须至少保留一种 2FA 方案：关闭最后一种会被拒绝；管理端「重置 2FA」不再清空，而是恢复默认邮箱验证码。未验证邮箱的账号仍可密码登录，验证邮箱后立即强制。若邮箱不可达，用户可用 TOTP 或恢复码完成登录；需灰度或回滚时参见 [设计文档](docs/superpowers/specs/2026-08-16-mandatory-2fa-design.md)。
- OIDC `access_token` 的 `aud` 从 `client_id` 改为 `{issuer}/oauth2/userinfo`，并已在 userinfo 端点强制校验。`id_token` 的 `aud` 仍为 `client_id`，不受影响。此前若对接方校验过 `access_token` 的 `aud == client_id`，发布后需同步更新为 userinfo 端点地址。详见 [对接指南 §2.5](docs/oidc-integration.md)。
- 技术标识统一为 `lipass`：Compose 项目/镜像/网络/命名卷由 `account-service` 系列改为 `lipass` 系列，从旧版升级需先按 [部署文档 §标识迁移](docs/deployment.md) 迁移数据卷；`acr` 声明由 `urn:portal-oss:acr:1fa/2fa` 改为 `urn:lipass:acr:1fa/2fa`，接入方在升级期按“两套值等价”校验，窗口过后只保留新值。

### 功能

- 注销/删除账号升级为「密码 + 任意 2FA」双因素复核：注销账号、管理端删除用户与批量删除必须同时提供当前密码与一种二次验证码（邮箱验证码或 TOTP），且**不享受 30 分钟免复核窗口**（每次必验）；新增 `POST /api/v1/me/step-up/send` 发送复核邮箱验证码（与登录 2FA 共用发送冷却与每小时配额），前端新增通用双因素复核表单（获取验证码 + 60 秒重发冷却）。设计见 [账号安全与体验改进设计](docs/superpowers/specs/2026-08-16-account-ux-security-improvements-design.md)。
- 密码输入实时强度显示（弱/中/强三段色条）：接入注册、邀请注册、找回密码、用户中心修改密码与管理员代建账号；按长度、大小写、数字、符号评分，仅显示、不改变后端密码策略。
- 注册完成自动跳转登录页并预填邮箱；未验证邮箱的用户登录后仍可在用户中心继续完成验证。
- 登录页新增「记住账号」「记住密码」选项：默认关闭、仅在登录成功后按勾选写入 localStorage（取消勾选即清除；勾选「记住密码」自动勾选「记住账号」）。密码本地明文保存存在同源 XSS 读取风险，已通过 CSP `script-src 'self'` 等缓解，仍建议优先使用浏览器密码管理器；权衡说明见设计文档。
- 强制 2FA 落地：验证邮箱（普通注册验证、邀请注册、管理员代建）后直接启用邮箱验证码作为默认第一方案；用户可升级到 TOTP 认证器，并可在两种方案并存时关闭其一，但不可清空全部。管理端「重置 2FA」恢复默认邮箱方案并清空 TOTP/恢复码。设计见 [强制二次验证设计](docs/superpowers/specs/2026-08-16-mandatory-2fa-design.md)，实施计划见 [实施计划](docs/superpowers/plans/2026-08-16-mandatory-2fa.md)。
- 敏感操作 step-up 复核窗口：新增 `GET/POST /api/v1/me/step-up`（复核窗口状态与显式密码复核端点）；一次密码复核成功后，该会话在 **30 分钟**内执行其它敏感操作免再次输入密码。窗口为固定时长、按会话隔离（一台设备复核不豁免其它设备）、**登录成功不自动授窗**。用户中心（修改密码/注销账号）、2FA 开关（邮箱验证码/TOTP）与全部管理端敏感操作（角色变更/重置密码/重置 2FA/删除用户/批量删除/删除客户端/重置密钥）统一接入；窗口时长与限流阈值可配置（`STEPUP_WINDOW_MINUTES=0` 可关闭窗口回到每操作必验）。设计见 [敏感操作 step-up 认证窗口设计](docs/superpowers/specs/2026-08-16-sensitive-stepup-window-design.md)，实施计划见 [实施计划](docs/superpowers/plans/2026-08-16-sensitive-stepup-window.md)。
- 联邦登出完整落地：RP 发起登出（`GET /oauth2/end-session` + 确认页 `/logout/confirm` + 精确匹配回跳白名单）、回程登出（`logout_token` 签发/异步分发/重试/SSRF 防护）、无回程网站的浏览器串跳漏斗、用户/管理员会话撤销与取消授权联动下线；`id_token` 新增 `sid`，发现文档新增 `end_session_endpoint`/`backchannel_logout_supported`；管理端新增「登出回跳白名单」「回程登出地址」配置，演示站实现对应 RP 侧示例。详见 [对接指南 §7](docs/oidc-integration.md) 与 [实施计划](docs/superpowers/plans/2026-08-15-federated-logout.md)。

### 安全加固

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
