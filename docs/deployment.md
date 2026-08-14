# 部署与运维

LinPass SSO 使用 Docker Compose 部署。仓库内置 `gateway`（nginx）作为**唯一对外入口**：前端、后端与演示站都不向宿主机映射端口，仅在容器内网互通；生产环境的 HTTPS 与域名由部署环境（K8s Ingress、云负载均衡、外部网关）负责，终止后转发到 gateway 的 80 端口。

## 架构

```text
浏览器 → [部署环境的 HTTPS / 反向代理，不属于本仓库]
          → gateway（nginx :80，本仓库唯一对外入口）
              ├── 前端服务（容器内 :5173，React 静态资源）
              ├── 后端服务（容器内 :8000，FastAPI /api /oauth2）
              └── 演示站（容器内 :3001，/demo）
后端 → PostgreSQL 16（数据）+ Redis 7（挑战/限流/待授权请求）
后端密钥卷：/app/keys（JWT 私钥 + Fernet 加密密钥）
后端上传卷：/app/uploads（用户头像）
命名卷（compose 项目固定为 `account-service`，卷名前缀 `account-service_`）：
`postgres-data-prod`、`redis-data-prod`、`backend-keys`、`backend-uploads`
```

## 一条命令启动（生产形态）

```bash
cp .env.example .env
# 按需修改 .env（域名、Cookie、邮件、密码等；生产配置示例见 .env.example 底部注释）
docker compose -f docker-compose.yaml --profile bundle --env-file .env up -d --build
```

开发与生产共用这一份 `docker-compose.yaml`：本地直接 `docker compose --profile bundle up -d --build`；生产按上文配置 `.env` 后再启动即可。使用远程 PostgreSQL/Redis 时去掉 `--profile bundle`。

启动后：

- 门户：http://localhost
- 健康检查：http://localhost/healthz（存活），http://localhost/readyz（就绪，含数据库/Redis 检查）

前端容器（nginx）内置安全响应头与 CSP：默认同源网关部署（`VITE_API_BASE_URL` 为空）时，前端、API 与头像资源同源加载；若改为独立后端域名，需同步更新 `VITE_API_BASE_URL` / `CONNECT_SRC` 并重建前端。

示例授权网站（仅本地演示）默认**不随生产栈启动**，需要时单独启用：

```bash
docker compose --profile bundle --profile demo up -d --build
# 演示网站：http://localhost/demo/
```

## 首次使用

1. 在门户注册账号并激活邮箱。
2. 提升管理员（运维脚本已内置在后端镜像）：

```bash
docker compose -f docker-compose.yaml --env-file .env exec backend \
  python -m scripts.make_admin <你的邮箱>
```

3. 创建演示客户端（可选，示例网站需要）：

```bash
docker compose -f docker-compose.yaml --env-file .env exec backend \
  python -m scripts.seed_demo_client
```

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `ENVIRONMENT` | `development` 或 `production`（生产启动时强校验，拼写错误会直接拒绝启动） |
| `PUBLIC_BASE_URL` | 对外门户地址（默认 `http://localhost`）；编排内自动派生 `FRONTEND_BASE_URL` / `JWT_ISSUER` |
| `FRONTEND_BASE_URL` | 门户前端地址（浏览器跳转用） |
| `JWT_ISSUER` | 后端签发地址，必须与对外域名一致 |
| `CORS_ORIGINS` | 允许的前端来源（JSON 数组） |
| `ALLOWED_HOSTS` | 后端接受的 Host 白名单（JSON 数组；生产必填真实域名，防 Host 头注入/DNS rebinding） |
| `SESSION_COOKIE_SECURE` | HTTPS 下必须 `true` |
| `SESSION_COOKIE_SAMESITE` | 见下方「SameSite 与部署拓扑」 |
| `SESSION_TTL_DAYS` / `SESSION_DEFAULT_TTL_DAYS` | 勾选“记住我”/未勾选时的会话有效期（默认 30 天 / 1 天；未勾选同时使用会话级 Cookie，关闭浏览器即失效） |
| `SESSION_IDLE_DAYS` | 会话空闲超时天数（默认 7 天，超过即强制下线） |
| `PUBLIC_REGISTRATION_ENABLED` | 公开注册入口默认值（默认 `true`）；`false` 时注册页提示“注册渠道暂时关闭，只接收邀请注册”，后端同时拒绝公开注册请求。管理后台「站点设置」可运行时覆盖该默认值（存入 `site_settings` 表） |
| `DATABASE_URL` / `REDIS_URL` | 数据与缓存连接串：留空时默认编排内 PostgreSQL/Redis（需 `bundle` profile）；填写远程地址即切换为远程实例 |
| `PENDING_REQUEST_STORE` / `TWOFA_STORE` / `RATE_LIMITER` | 生产用 `redis` |
| `ADMIN_INVITE_RATE_LIMIT` / `ADMIN_INVITE_RATE_WINDOW_SECONDS` | 管理端邀请限流（按来源 IP 计，批量邀请按人数累计；默认 100 次/小时） |
| `LOGIN_RATE_LIMIT` / `LOGIN_RATE_WINDOW_SECONDS` | 按邮箱+IP 的登录失败次数限流（默认 5 次/15 分钟，第 6 次失败返回 429） |
| `LOGIN_IP_RATE_LIMIT` / `LOGIN_IP_RATE_WINDOW_SECONDS` | 按来源 IP 的登录尝试次数限流（默认 20 次/15 分钟，在 Argon2 之前前置拦截） |
| `LOGIN_EMAIL_RATE_LIMIT` / `LOGIN_EMAIL_RATE_WINDOW_SECONDS` | 全局限邮箱登录限流，防分布式 IP 爆破（默认 10 次/15 分钟）。注意这是短时账号级锁定：窗口内对同一邮箱的尝试超过阈值后，无论来源 IP 都会被拒绝，攻击者可用错误密码尝试暂时锁住目标账号；需在防爆破与可用性之间权衡 |
| `CLIENT_BLOCK_RATE_LIMIT` / `CLIENT_BLOCK_RATE_WINDOW_SECONDS` | OAuth 客户端黑名单接口限流（默认 100 次/小时/client_id）。计数包含列表（GET）接口，高频轮询同样计入 |
| `AUDIT_RETENTION_DAYS` | 审计日志保留天数，超期由后台维护任务删除（默认 180，且必须 ≥1 无法关闭）。安全审计痕迹到期即删，合规要求长期留存时请显式调大 |
| `SESSION_RETENTION_DAYS` | 已吊销/已过期会话保留天数，超期由后台维护任务删除（默认 30）。空闲超时会话在访问时惰性吊销，此处按过期时间兜底删除 |
| `AVATAR_CLEANUP_INTERVAL_SECONDS` | 孤儿头像清理周期（秒）；`0` 关闭周期任务，仍保留启动时清理一次（默认 21600）。该周期任务同时负责审计日志与已下线会话的保留期清理，设为 `0` 会一并停掉这些周期清理 |
| `EPHEMERAL_RETENTION_HOURS` | 过期 OTP/授权码/邀请的保留期（小时），超期由后台维护任务删除（默认 168） |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | SQLAlchemy 连接池大小（默认 `5` + `10`；提高 worker 数时应同步放大） |
| `UVICORN_WORKERS` | 后端 uvicorn worker 数（默认 `1`；使用 memory 存储的本地模式必须保持 1） |
| `IP2REGION_DATA_DIR` | ip2region 数据目录（生产必须为绝对路径，默认 `/app/data/ip2region`，构建期已内置 v3.17.0） |
| `IP2REGION_AUTO_UPDATE_ENABLED` | 自动更新默认开关（默认 `false`，可在站点设置运行时覆盖） |
| `IP2REGION_UPDATE_INTERVAL_HOURS` | 自动检查间隔（默认 `24`，范围 1–8760） |
| `IP2REGION_RELEASES_API_URL` / `IP2REGION_DOWNLOAD_BASE_URL` | 版本发现与下载源（默认 GitHub，被墙环境可切 Gitee 镜像） |
| `JWT_PRIVATE_KEY_PATH` / `ENCRYPTION_KEY_PATH` | 密钥文件路径（生产必须为绝对路径，指向 `/app/keys` 卷） |
| `JWT_KEYS_DIR` / `JWT_ACTIVE_KID` | 可选密钥轮换：目录内每个 `*.pem` 文件名即 kid；`JWT_ACTIVE_KID` 指定签名 kid（缺省取字典序最大），详见「密钥管理」 |
| `EMAIL_BACKEND` | `console`（开发）或 `smtp`（生产） |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 服务器地址与端口（生产必填） |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP 登录凭据（按需） |
| `SMTP_FROM` / `SMTP_FROM_NAME` | 真实发件地址与发件人名称（生产必填 `SMTP_FROM`） |
| `SMTP_USE_TLS` | 是否使用 STARTTLS（默认 `true`） |
| `SMTP_TIMEOUT_SECONDS` | 单次 SMTP 操作超时（默认 `15`，建议保持 10–20） |
| `SMTP_MAX_RETRIES` | 瞬时连接失败的自动重试次数（默认 `2`，范围 0–5） |
| `SMTP_RETRY_DELAY_SECONDS` | 重试间隔秒数（默认 `1`） |
| `REDIS_PASSWORD` | Redis AUTH 口令，生产必须设置长度 ≥12 的强口令 |
| `REDIS_MAXMEMORY` | 编排内 Redis 内存上限（默认 `192mb`，只淘汰带 TTL 的键） |
| `REDIS_APPENDONLY` | 编排内 Redis AOF 持久化开关（默认 `yes`） |
| `FORWARDED_ALLOW_IPS` | 反向代理 IP/CIDR 白名单；编排内默认只信任网关固定 IP `172.30.0.10`（compose 固定子网），使用外部反代时改为其网关 IP 或网段 |

## IP 归属地库（ip2region）

- 用途：会话监控与审计日志的 IP 归属地展示、数据统计的登录地域分布；查询完全离线。
- 数据与内存：IPv4 + IPv6 两份 xdb 共约 48MB，进程内懒加载并常驻（每个 uvicorn worker 各一份）；提高 `UVICORN_WORKERS` 时按 48MB/worker 评估容器内存上限。
- 更新：构建镜像时用固定 tag + SHA256 校验内置 v3.17.0；管理后台「站点设置 → IP 归属地库」可手动「立即检查更新」，或开启自动更新（默认关闭，间隔 24 小时）。**运行期更新同样强制 SHA256 校验**：只有列入代码内信任清单（`app/services/ip2region_pins.py`）的版本才允许安装，清单外的上游新版本一律拒绝（宁可停止更新也不装入未审计数据）；上游发布新版本后需先在构建流程中固定哈希并更新清单，再发布应用。更新采用下载到临时目录 → 结构校验 → SHA256 校验 → 先备份再原子替换（失败自动回滚旧库）→ 更新 meta.json，全程由跨进程文件锁互斥（多 worker 安全）；手动更新按管理员限流（默认 6 次/小时）并记审计。
- 内网部署：GitHub 不可达时把 `IP2REGION_RELEASES_API_URL` 与 `IP2REGION_DOWNLOAD_BASE_URL` 指向 Gitee 镜像（见 `.env.example`），或完全关闭自动更新、仅在构建时随镜像更新。

## 编排内 / 远程数据库切换

默认的全栈启动使用编排内服务，PostgreSQL 与 Redis 位于 `bundle` profile：

```bash
docker compose --profile bundle up -d --build
```

后端容器内默认连接串为：

- `DATABASE_URL=postgresql+psycopg://…@postgres:5432/portal`
- `REDIS_URL=redis://:…@redis:6379/0`

若使用云数据库、托管 Redis 或自建远程实例，在 `.env` 中显式覆盖连接串，并去掉 `--profile bundle`，Compose 将不会启动编排内的 postgres/redis（backend 的 `depends_on` 已标记 `required: false`）：

```bash
# .env
DATABASE_URL=postgresql+psycopg://user:password@db.example.com:5432/portal
REDIS_URL=redis://:password@redis.example.com:6379/0

docker compose up -d --build
```

两种模式可以随时切换，数据不互迁：编排内连接使用 `postgres-data-prod` / `redis-data-prod` 卷，远程连接完全由 `DATABASE_URL` / `REDIS_URL` 决定。

生产邮箱配置示例：

```text
EMAIL_BACKEND=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=noreply@example.com
SMTP_PASSWORD=******
SMTP_FROM=noreply@example.com
SMTP_FROM_NAME=LinPass SSO
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=15
SMTP_MAX_RETRIES=2
SMTP_RETRY_DELAY_SECONDS=1
```

邮件分为两类：注册/登录/重置/绑手机等场景发送 6 位验证码（10 分钟有效，重发会作废旧码）；邀请注册发送一次性邀请链接（7 天有效）。各发送接口的限流口径不同：

- 登录后 2FA 验证码、手机绑定验证码：`OTP_SEND_LIMIT=5` 次/小时/邮箱；2FA 进入二次验证页不自动发信，需用户点击“获取验证码”，重发最小间隔 `OTP_RESEND_COOLDOWN_SECONDS`（默认 60 秒）
- 登录失败：每邮箱+IP `LOGIN_RATE_LIMIT=5` 次/15 分钟（第 6 次失败返回 429），每 IP `LOGIN_IP_RATE_LIMIT=20` 次/15 分钟，全局限邮箱 `LOGIN_EMAIL_RATE_LIMIT=10` 次/15 分钟；邮箱级限流附带短时账号锁定权衡，见上表说明
- 邮箱激活验证码重发与验证尝试：`EMAIL_VERIFY_RATE_LIMIT=30` 次/小时/邮箱（不按 IP 限流，避免办公网/NAT 共享出口误伤）
- 注册/邀请注册接口：`REGISTER_RATE_LIMIT=10` 次/小时/IP
- 找回密码：`PASSWORD_RESET_RATE_LIMIT=5` 次/小时/邮箱（不按 IP 限流）
- 管理端邀请：`ADMIN_INVITE_RATE_LIMIT=100` 次/小时/IP（批量邀请按人数累计）

## BIMI 发件人头像（品牌 Logo）

门户已内置 BIMI 合规的矢量 Logo（`frontend/public/bimi/logo.svg`，SVG Tiny P/S、方形纯色底、≤32KB），随前端构建发布，经 `https://<你的域名>/bimi/logo.svg` 对外提供。要让邮箱客户端在收件箱显示品牌发件头像，需完成两步：

1. **DMARC 强制策略**：域名需有对齐的 SPF/DKIM，且 DMARC 策略为 `p=quarantine` 或 `p=reject`。
2. **BIMI DNS 记录**：在 DNS 添加 TXT 记录（把域名替换为真实域名）：

   ```text
   default._bimi  IN  TXT  "v=BIMI1; l=https://portal.example.com/bimi/logo.svg"
   ```

说明：

- Gmail / Apple Mail 显示 BIMI 头像还需要 Verified Mark Certificate（VMC）：取得 VMC 后在其 PEM 文件 URL 加 `a=` 段，例如 `v=BIMI1; l=https://portal.example.com/bimi/logo.svg; a=https://portal.example.com/bimi/vmc.pem`；Yahoo 等无需 VMC 即可显示。
- 尚未取得 VMC 时可以先只写 `l=` 段，不影响发信与认证。
- 更换 Logo 时直接替换 `frontend/public/bimi/logo.svg` 重新发布即可，无需改 DNS（静态缓存 7 天）。

## SameSite 与部署拓扑（重要）

门户会话 Cookie 的 `SameSite` 属性取决于前端与后端的域名关系：

- **同站部署（推荐，安全默认）**：前端与后端在同一可注册域名下，例如 `portal.example.com`（前端）与 `api.portal.example.com` 或同域不同路径（后端）。此时
  `SESSION_COOKIE_SAMESITE=lax`，跨站 CSRF 风险最小。
- **跨站部署**：前端 `portal.example.com`、后端 `auth.example.com`（完全不同域名）。浏览器跨站 XHR 不携带 `Lax` Cookie，门户会表现为无法登录，此时必须
  `SESSION_COOKIE_SAMESITE=none` 且 `SESSION_COOKIE_SECURE=true`（HTTPS）。`none` 会放大 CSRF 风险，本仓库已通过「带会话 Cookie 的写请求必须校验 Origin」中间件兜底。

生产环境后端会拒绝 `lax/strict/none` 之外的取值，并拒绝「`none` 未配 HTTPS」的组合。

## 密钥管理

- JWT 私钥与 Fernet 密钥首次启动时自动生成，写入 `backend-keys` 命名卷（容器内 `/app/keys`）。
- **必须备份该卷**：

```bash
docker run --rm -v account-service_backend-keys:/keys -v "$PWD":/backup alpine \
  tar czf /backup/backend-keys.tar.gz -C /keys .
```

- 丢失 JWT 私钥：所有已签发 access token 失效，需重新部署并让用户重新登录。
- 丢失 Fernet 密钥：已加密的 TOTP 密钥无法解密，管理员需逐个重置用户 2FA。
- 生产环境强制密钥路径为绝对路径（默认 `/app/keys/…`），避免工作目录变化导致密钥漂移。

### JWT 签名密钥轮换

单文件模式使用固定 kid `portal-rs256-1`。需要轮换时切换到目录模式：

1. 把现有私钥重命名为 `portal-rs256-1.pem` 放入密钥目录（如 `/app/keys/jwt/`，仍位于 `backend-keys` 卷内），配置 `JWT_KEYS_DIR=/app/keys/jwt`。
2. 在 backend 容器内生成下一把密钥：

   ```bash
   docker compose exec backend python -m scripts.rotate_jwt_key
   ```

   脚本生成 `portal-rs256-2.pem`（依次递增）并打印发布步骤。
3. 设置 `JWT_ACTIVE_KID=portal-rs256-2` 并滚动重启 backend。新进程用新 kid 签名；JWKS 端点会同时发布目录内全部公钥，旧 kid 签发的 token 仍可验证。
4. 等待超过 access token 最长有效期（15 分钟，建议 1 小时）后，删除目录内旧 `*.pem` 文件并再次滚动重启。`JWT_ACTIVE_KID` 必须始终指向目录中存在的密钥。

注意事项：密钥目录在进程内按路径缓存，新增/删除密钥后必须重启进程生效；不要在多个 worker 进程同时跑轮换脚本（`atomic_write` 的独占创建会保证只生成一次，但应避免并发执行）。

## PostgreSQL 备份与恢复

以下命令仅适用于编排内 PostgreSQL（`--profile bundle`）；使用远程 PostgreSQL 时，请使用云厂商或实例自带的备份机制。

备份：

```bash
docker compose -f docker-compose.yaml --env-file .env exec postgres \
  pg_dump -U portal portal | gzip > portal-$(date +%Y%m%d-%H%M%S).sql.gz
```

恢复：

```bash
gunzip -c portal-20260101-120000.sql.gz | \
  docker compose -f docker-compose.yaml --env-file .env exec -T postgres \
  psql -U portal portal
```

建议配置定时任务（cron/云备份）并定期演练恢复。用户头像存储在 `backend-uploads` 卷，同样需要备份：

```bash
docker run --rm -v account-service_backend-uploads:/uploads -v "$PWD":/backup alpine \
  tar czf /backup/backend-uploads.tar.gz -C /uploads .
```

仓库提供一键备份/恢复脚本（仅编排内 PostgreSQL，`--profile bundle`）：

```bash
bash scripts/backup-db.sh                  # 备份到 backups/portal-<时间戳>.sql.gz
bash scripts/restore-db.sh backups/portal-20260813-120000.sql.gz
```

## 数据库迁移与升级策略

迁移为单链增量结构（当前 head 为 `6d1f9c0b2e4a`，含管理后台统计所需的审计日志复合索引）。后续开发版本必须遵循以下规则，保证平滑升级且不丢数据：

1. **所有结构变更都走 Alembic 增量迁移**：禁止手工改生产库，也禁止用 `Base.metadata.create_all` 初始化已有库。后端启动命令已内置 `alembic upgrade head`，新版本上线时自动升级到最新结构。
2. **迁移必须可降级**：每个迁移的 `downgrade()` 要完整可执行；无法安全回退的结构变更要写成“先加后删”的两阶段迁移（expand → migrate → contract），而不是一步重命名/删列。
3. **新增 NOT NULL 列必须带 `server_default` 或先 nullable 再回填**，避免对存量行直接失败；枚举/状态新增取值只能追加，不能删除旧值。
4. **禁止在迁移里清理业务数据**：例如删除用户、清空 OTP、重置会话等属于运维动作，不应放进 schema 迁移。
5. **升级前必须备份**：执行 `bash scripts/backup-db.sh`，并确认 `backend-keys` / `backend-uploads` 卷已有备份。
6. **迁移只执行一次**：单实例可依赖后端启动自动迁移；多副本部署应在发布流程中单独执行一次 `docker compose run --rm backend alembic upgrade head`，再扩容副本。
7. **升级后验证**：检查 `/readyz`、查看 `alembic current` 是否等于代码 head，并抽样验证登录/注册/授权主流程。

推荐升级流程：

```bash
# 1. 备份
bash scripts/backup-db.sh

# 2. 拉取新代码并重建启动（后端启动时自动执行 alembic upgrade head）
docker compose --profile bundle up -d --build

# 3. 确认迁移版本
docker compose --profile bundle exec backend alembic current
```

如需回滚到上一个迁移版本（先确认新迁移对数据的破坏范围，必要时用备份恢复）：

```bash
docker compose --profile bundle exec backend alembic downgrade -1
```

## 容器数据持久化说明

| 服务 | 数据内容 | 存储位置 | 重建容器后 |
| --- | --- | --- | --- |
| PostgreSQL | 用户/会话/OAuth/审计/授权记录 | `account-service_postgres-data-prod`（`/var/lib/postgresql/data`） | 数据保留 |
| Redis | 验证码、2FA 挑战、待授权请求、限流计数 | `account-service_redis-data-prod`（`/data`，RDB + AOF） | 数据保留（短 TTL 数据本就过期） |
| 后端 | JWT 私钥、Fernet 加密密钥 | `account-service_backend-keys`（`/app/keys`） | 密钥保留 |
| 后端 | 用户头像 | `account-service_backend-uploads`（`/app/uploads`） | 头像保留 |
| 后端 | ip2region 离线库（含运行期更新结果） | `account-service_backend-data`（`/app/data`） | 保留（首次挂载自动带入镜像内置数据） |
| 前端 nginx | 无（仅静态构建产物） | 容器层 | 重建后由镜像重新提供 |
| 示例授权网站 | 无 | 容器层 | 重建后恢复默认 |

Redis 已通过 `--appendonly yes` 显式开启 AOF（可用 `REDIS_APPENDONLY=no` 关闭）。验证码/挑战/限流本身是短生命周期数据，即使丢失也只是要求用户重试，**唯一不可再生的数据是 PostgreSQL 与后端密钥卷**。

⚠️ 停止容器不会删数据，但 **`docker compose down -v` 会删除全部命名卷**（数据库、密钥、头像一次性清空且难以恢复）。删除卷前务必先备份并确认。

## HTTPS 与反向代理

仓库内置的 gateway（nginx）只做 HTTP 路由，不负责 TLS 终止。生产上线时：

1. 在部署环境配置 TLS 与路由（例如 K8s Ingress、云负载均衡或外部网关），把域名指向前端与后端服务。
2. **HSTS 双保险**：
   - 后端在 `SESSION_COOKIE_SECURE=true`（生产必填）时自动签发 `Strict-Transport-Security: max-age=63072000; includeSubDomains`，覆盖全部 API 响应；
   - 如需让网关在**所有**响应（含前端 HTML）上再签发一层，在 `.env` 设置 `HSTS_MAX_AGE=63072000`（开发/HTTP 直连时保持留空，避免误发；浏览器按规范只在 HTTPS 连接上生效）。
3. 更新 `.env`（参考 `.env.example` 底部的生产配置示例）：
   - `ENVIRONMENT=production`
   - `JWT_ISSUER=https://auth.example.com`
   - `FRONTEND_BASE_URL=https://portal.example.com`
   - `CORS_ORIGINS=["https://portal.example.com"]`
   - `ALLOWED_HOSTS=["portal.example.com","127.0.0.1"]`（真实域名必填；`127.0.0.1` 供容器健康检查）
   - `SESSION_COOKIE_SECURE=true`
   - `SESSION_COOKIE_SAMESITE`：按「SameSite 与部署拓扑」选择 `lax` 或 `none`
   - `FORWARDED_ALLOW_IPS`：使用编排内网关时保持默认（`172.30.0.10`）；改用外部反代时填网关 IP/CIDR，让限流/审计拿到真实客户端 IP
4. 重新构建并启动。

### 外部 nginx 终止 TLS 的参考配置

若使用自建 nginx 终止 HTTPS，推荐以下要点（密钥交换曲线把 `X25519` 放在首位，避免协商到较弱的 `secp256r1`/`prime256v1`）：

```nginx
server {
    listen 443 ssl;
    http2 on;
    server_name portal.example.com;

    ssl_certificate     /etc/letsencrypt/live/portal.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/portal.example.com/privkey.pem;

    # 只启用 TLS 1.2/1.3；曲线优先 X25519
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ecdh_curve X25519:prime256v1:secp384r1;

    # 会话复用与 OCSP 装订（减少握手开销并保护隐私）
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;
    ssl_stapling on;
    ssl_stapling_verify on;

    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name portal.example.com;
    return 301 https://$host$request_uri;
}
```

更完整的参数建议参考 [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)（选择 nginx + modern）。

### Let's Encrypt 证书与自动续期

Let's Encrypt 证书有效期只有 90 天，必须配置可靠的自动续期，否则证书过期会导致全站不可用。certbot 默认安装的 systemd timer 每天会尝试两次续期，但仍建议显式配置并定期巡检：

```bash
# 签发（nginx 插件会自动改写配置并配置续期）
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d portal.example.com

# 验证自动续期可用（不会真正续期）
sudo certbot renew --dry-run

# 续期后重载 nginx：编辑续期钩子，保证新证书生效
sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh > /dev/null <<'EOF'
#!/bin/sh
systemctl reload nginx
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
```

监控建议：对 `certbot certificates` 输出或证书文件做到期检查（例如每日 cron 里 `openssl x509 -enddate` 判断剩余天数），小于 30 天即告警；同时确认 80 端口的 ACME 验证路径在防火墙/负载均衡层可达。

## 上线前安全清单

- [ ] `ENVIRONMENT=production`，且启动日志无配置校验错误
- [ ] `SESSION_COOKIE_SECURE=true`；SameSite 按拓扑选择并理解后果
- [ ] `CORS_ORIGINS` 仅含真实 HTTPS 来源；`FORWARDED_ALLOW_IPS` 仅含自己的网关 IP
- [ ] `ALLOWED_HOSTS` 仅含真实域名
- [ ] PostgreSQL / Redis 使用长度 ≥12 的独立强口令；Redis 已启用 AUTH
- [ ] `EMAIL_BACKEND=smtp` 且 SMTP 可真实发信（未验证邮箱的用户无法完成 OIDC 授权）
- [ ] `PUBLIC_BASE_URL` 为真实对外地址（不是 `localhost`），否则邀请邮件链接无法访问；启动日志中不应出现“FRONTEND_BASE_URL 指向本机”警告
- [ ] 发信域名已配置 SPF，并尽量开启 DKIM/DMARC（阿里企业邮箱控制台开启；缺失时邮件易进垃圾箱或被拒收）
- [ ] 已按合规要求评估 `AUDIT_RETENTION_DAYS`（默认 180 天，审计日志到期自动删除）
- [ ] 已评估 `LOGIN_EMAIL_RATE_LIMIT` 的账号锁定权衡（防爆破 vs 短时拒绝目标账号登录）
- [ ] 已备份 `backend-keys` 与 `backend-uploads` 卷，并演练过恢复
- [ ] 网关已配置 TLS、HSTS、HTTP→HTTPS 跳转（后端生产会自动签发 HSTS；可用 `curl -sI https://域名/api/v1/healthz | grep -i strict-transport` 验证）
- [ ] TLS 曲线以 X25519 优先（`openssl s_client -connect 域名:443 -tls1_3` 协商结果非 secp256r1/prime256v1；或按上文 nginx 参考配置显式声明 `ssl_ecdh_curve`）
- [ ] Let's Encrypt 续期可用：`certbot renew --dry-run` 通过，续期钩子已重载 nginx，并配置到期监控（<30 天告警）
- [ ] 网关已放行 `/readyz`（或仅内部可达），不要把 `/docs` 暴露（生产已自动关闭）
- [ ] 用 `docker compose config` 检查渲染后的编排，确认没有把演示站点带进生产栈

## 常见运维操作

- 查看日志：`docker compose -f docker-compose.yaml --env-file .env logs -f backend`
- 查看健康状态：`docker compose -f docker-compose.yaml --env-file .env ps`
- 后台维护：后端启动时自动清理一次孤儿头像、过期 OTP/授权码/邀请、超期审计日志与已下线会话，之后按 `AVATAR_CLEANUP_INTERVAL_SECONDS`（默认 6 小时）周期执行；设为 `0` 时上述周期清理全部停用（仅保留启动时一次）。可在日志中查看“头像自动清理 / 临时凭证清理”记录
- 用户与邀请：邀请注册/批量邀请、批量启用/禁用/删除、账号注销均在门户界面完成（管理后台 → 用户管理；用户中心 → 注销账号）
- 升级：`bash scripts/backup-db.sh` 备份后，拉取新代码执行 `docker compose --profile bundle up -d --build`，后端启动时会自动执行 `alembic upgrade head`
- 迁移回滚：`docker compose --profile bundle exec backend alembic downgrade -1`（先评估数据影响，必要时用备份恢复）
- 多副本部署：迁移应在发布流程中只执行一次（例如 `docker compose run --rm backend alembic upgrade head`），再扩容后端副本；单实例部署可继续依赖启动自动迁移
- 审计查询：管理员登录门户后调用 `GET /api/v1/admin/audit-logs`（或直接查 `audit_logs` 表）

## 容器镜像版本固定

`docker-compose.yaml` 的所有镜像地址统一由一个环境变量 `IMAGE_REGISTRY` 控制（默认留空 = 官方 Docker Hub）。它会同时作用于：

- 基础设施镜像：`postgres:16-alpine`、`redis:7-alpine`
- 自建服务镜像：`account-service-backend:local`、`account-service-frontend:local`、`account-service-demo-site:local`（同时作为 `docker compose build` 的标签）
- 构建基础镜像：`python:3.12-slim`、`node:22-alpine`（前端依赖要求 Node ≥22.14）、`nginx:1.27-alpine`（作为构建参数传入 Dockerfile）

私有仓库 / 内网镜像源场景只需在 `.env` 设置一个变量（**必须以 `/` 结尾**）：

  ```text
  IMAGE_REGISTRY=registry.example.com/
  ```

渲染后的镜像地址示例：`registry.example.com/postgres:16-alpine`、`registry.example.com/account-service-backend:local`。

本地构建并推送：先构建并推送到私有仓库，生产端设置同一 `IMAGE_REGISTRY` 直接拉取：

```bash
docker compose build
docker compose push
```

若需要按镜像锁定具体 digest（例如 `registry.example.com/postgres@sha256:…`），可在编排文件中直接改写对应 `image:` 行，或使用私有仓库的不可变 tag（如 `v1.0.0`）配合 CI 人工评审升级。
