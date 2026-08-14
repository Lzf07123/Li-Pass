# 更新日志

## 未发布（开发中）

### 破坏性变更

- OIDC `access_token` 的 `aud` 从 `client_id` 改为 `{issuer}/oauth2/userinfo`，并已在 userinfo 端点强制校验。`id_token` 的 `aud` 仍为 `client_id`，不受影响。此前若对接方校验过 `access_token` 的 `aud == client_id`，发布后需同步更新为 userinfo 端点地址。详见 [对接指南 §2.5](docs/oidc-integration.md)。

### 安全加固

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

- 桌面端留白优化：已登录页面统一放宽内容区宽度——管理后台、用户中心、收件箱由 `max-w-5xl/4xl/3xl` 统一为 `max-w-7xl`（1280px），顶栏/骨架屏/页脚同步，并新增 `lg:px-8` 大屏内边距；登录/注册/授权确认等表单页保持窄版（`max-w-md`）不变。
- 管理后台「用户管理」新增「刷新」按钮：按当前搜索词与筛选条件重新拉取用户列表，加载中禁用、成功/失败均有提示，与会话监控等其他管理面板保持一致。设计见 [用户管理刷新按钮设计](docs/superpowers/specs/2026-08-14-admin-users-refresh-button-design.md)。
- pip 源切换为中科大镜像 `https://mirrors.ustc.edu.cn/pypi/simple`：后端与演示站镜像构建通过 `PIP_INDEX_URL` 构建参数使用（海外构建可改回官方源），本地开发步骤同步更新；CI 保持官方 PyPI（GitHub 托管 runner 在海外走镜像更慢）。
- 前端镜像构建优化：构建基础镜像 `node:20-alpine → node:22-alpine`（消除 jsdom 依赖链的引擎不匹配警告，与 CI 对齐），`npm ci` 启用 BuildKit 缓存挂载并跳过 audit/fund 网络往返，重建提速；`package.json` 显式声明 `engines.node >=22.14.0`。
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
