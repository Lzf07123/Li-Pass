# 部署与运维

Portal OSS 使用 Docker Compose 部署。仓库内置 `gateway`（nginx）作为**唯一对外入口**：前端、后端与演示站都不向宿主机映射端口，仅在容器内网互通；生产环境的 HTTPS 与域名由部署环境（K8s Ingress、云负载均衡、外部网关）负责，终止后转发到 gateway 的 80 端口。

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
命名卷（compose 项目固定为 `portal-oss`，卷名前缀 `portal-oss_`）：
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
| `FRONTEND_BASE_URL` | 门户前端地址（浏览器跳转用） |
| `JWT_ISSUER` | 后端签发地址，必须与对外域名一致 |
| `CORS_ORIGINS` | 允许的前端来源（JSON 数组） |
| `ALLOWED_HOSTS` | 后端接受的 Host 白名单（JSON 数组；生产必填真实域名，防 Host 头注入/DNS rebinding） |
| `SESSION_COOKIE_SECURE` | HTTPS 下必须 `true` |
| `SESSION_COOKIE_SAMESITE` | 见下方「SameSite 与部署拓扑」 |
| `SESSION_TTL_DAYS` / `SESSION_DEFAULT_TTL_DAYS` | 勾选“记住我”/未勾选时的会话有效期（默认 30 天 / 1 天；未勾选同时使用会话级 Cookie，关闭浏览器即失效） |
| `SESSION_IDLE_DAYS` | 会话空闲超时天数（默认 7 天，超过即强制下线） |
| `DATABASE_URL` / `REDIS_URL` | 数据与缓存连接串：留空时默认编排内 PostgreSQL/Redis（需 `bundle` profile）；填写远程地址即切换为远程实例 |
| `PENDING_REQUEST_STORE` / `TWOFA_STORE` / `RATE_LIMITER` | 生产用 `redis` |
| `ADMIN_INVITE_RATE_LIMIT` / `ADMIN_INVITE_RATE_WINDOW_SECONDS` | 管理端邀请限流（按来源 IP 计，批量邀请按人数累计；默认 100 次/小时） |
| `JWT_PRIVATE_KEY_PATH` / `ENCRYPTION_KEY_PATH` | 密钥文件路径（生产必须为绝对路径，指向 `/app/keys` 卷） |
| `EMAIL_BACKEND` | `console`（开发）或 `smtp`（生产） |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 服务器地址与端口（生产必填） |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP 登录凭据（按需） |
| `SMTP_FROM` / `SMTP_FROM_NAME` | 真实发件地址与发件人名称（生产必填 `SMTP_FROM`） |
| `SMTP_USE_TLS` | 是否使用 STARTTLS（默认 `true`） |
| `REDIS_PASSWORD` | Redis AUTH 口令，生产必须设置长度 ≥12 的强口令 |
| `FORWARDED_ALLOW_IPS` | 反向代理 IP/CIDR 白名单；编排内默认只信任网关固定 IP `172.30.0.10`（compose 固定子网），使用外部反代时改为其网关 IP 或网段 |

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
SMTP_FROM_NAME=Portal OSS
SMTP_USE_TLS=true
```

邮件内容包含 6 位验证码，10 分钟有效；发送接口受每小时 5 次/邮箱的限流保护。

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
docker run --rm -v portal-oss_backend-keys:/keys -v "$PWD":/backup alpine \
  tar czf /backup/backend-keys.tar.gz -C /keys .
```

- 丢失 JWT 私钥：所有已签发 access token 失效，需重新部署并让用户重新登录。
- 丢失 Fernet 密钥：已加密的 TOTP 密钥无法解密，管理员需逐个重置用户 2FA。
- 生产环境强制密钥路径为绝对路径（默认 `/app/keys/…`），避免工作目录变化导致密钥漂移。

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
docker run --rm -v portal-oss_backend-uploads:/uploads -v "$PWD":/backup alpine \
  tar czf /backup/backend-uploads.tar.gz -C /uploads .
```

仓库提供一键备份/恢复脚本（仅编排内 PostgreSQL，`--profile bundle`）：

```bash
bash scripts/backup-db.sh                  # 备份到 backups/portal-<时间戳>.sql.gz
bash scripts/restore-db.sh backups/portal-20260813-120000.sql.gz
```

## 数据库迁移与升级策略

当前为初版（`alembic` 迁移版本 `9a1b2c3d4e5f`）。后续开发版本必须遵循以下规则，保证平滑升级且不丢数据：

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
| PostgreSQL | 用户/会话/OAuth/审计/授权记录 | `portal-oss_postgres-data-prod`（`/var/lib/postgresql/data`） | 数据保留 |
| Redis | 验证码、2FA 挑战、待授权请求、限流计数 | `portal-oss_redis-data-prod`（`/data`，RDB + AOF） | 数据保留（短 TTL 数据本就过期） |
| 后端 | JWT 私钥、Fernet 加密密钥 | `portal-oss_backend-keys`（`/app/keys`） | 密钥保留 |
| 后端 | 用户头像 | `portal-oss_backend-uploads`（`/app/uploads`） | 头像保留 |
| 前端 nginx | 无（仅静态构建产物） | 容器层 | 重建后由镜像重新提供 |
| 示例授权网站 | 无 | 容器层 | 重建后恢复默认 |

Redis 已通过 `--appendonly yes` 显式开启 AOF（可用 `REDIS_APPENDONLY=no` 关闭）。验证码/挑战/限流本身是短生命周期数据，即使丢失也只是要求用户重试，**唯一不可再生的数据是 PostgreSQL 与后端密钥卷**。

⚠️ 停止容器不会删数据，但 **`docker compose down -v` 会删除全部命名卷**（数据库、密钥、头像一次性清空且难以恢复）。删除卷前务必先备份并确认。

## HTTPS 与反向代理

仓库不包含反代组件。生产上线时：

1. 在部署环境配置 TLS 与路由（例如 K8s Ingress、云负载均衡或外部网关），把域名指向前端与后端服务。
2. **HSTS 必须在网关侧配置**（例如 `Strict-Transport-Security: max-age=63072000; includeSubDomains`），仓库内前端/后端不直接签发，避免 HTTP 直连时误发。
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

## 上线前安全清单

- [ ] `ENVIRONMENT=production`，且启动日志无配置校验错误
- [ ] `SESSION_COOKIE_SECURE=true`；SameSite 按拓扑选择并理解后果
- [ ] `CORS_ORIGINS` 仅含真实 HTTPS 来源；`FORWARDED_ALLOW_IPS` 仅含自己的网关 IP
- [ ] `ALLOWED_HOSTS` 仅含真实域名
- [ ] PostgreSQL / Redis 使用长度 ≥12 的独立强口令；Redis 已启用 AUTH
- [ ] `EMAIL_BACKEND=smtp` 且 SMTP 可真实发信（未验证邮箱的用户无法完成 OIDC 授权）
- [ ] 已备份 `backend-keys` 与 `backend-uploads` 卷，并演练过恢复
- [ ] 网关已配置 TLS、HSTS、HTTP→HTTPS 跳转
- [ ] 网关已放行 `/readyz`（或仅内部可达），不要把 `/docs` 暴露（生产已自动关闭）
- [ ] 用 `docker compose config` 检查渲染后的编排，确认没有把演示站点带进生产栈

## 常见运维操作

- 查看日志：`docker compose -f docker-compose.yaml --env-file .env logs -f backend`
- 查看健康状态：`docker compose -f docker-compose.yaml --env-file .env ps`
- 升级：`bash scripts/backup-db.sh` 备份后，拉取新代码执行 `docker compose --profile bundle up -d --build`，后端启动时会自动执行 `alembic upgrade head`
- 迁移回滚：`docker compose --profile bundle exec backend alembic downgrade -1`（先评估数据影响，必要时用备份恢复）
- 多副本部署：迁移应在发布流程中只执行一次（例如 `docker compose run --rm backend alembic upgrade head`），再扩容后端副本；单实例部署可继续依赖启动自动迁移
- 审计查询：管理员登录门户后调用 `GET /api/v1/admin/audit-logs`（或直接查 `audit_logs` 表）

## 容器镜像版本固定

`docker-compose.yaml` 的所有镜像地址统一由一个环境变量 `IMAGE_REGISTRY` 控制（默认留空 = 官方 Docker Hub）。它会同时作用于：

- 基础设施镜像：`postgres:16-alpine`、`redis:7-alpine`
- 自建服务镜像：`portal-oss-backend:local`、`portal-oss-frontend:local`、`portal-oss-demo-site:local`（同时作为 `docker compose build` 的标签）
- 构建基础镜像：`python:3.12-slim`、`node:20-alpine`、`nginx:1.27-alpine`（作为构建参数传入 Dockerfile）

私有仓库 / 内网镜像源场景只需在 `.env` 设置一个变量（**必须以 `/` 结尾**）：

  ```text
  IMAGE_REGISTRY=registry.example.com/
  ```

渲染后的镜像地址示例：`registry.example.com/postgres:16-alpine`、`registry.example.com/portal-oss-backend:local`。

本地构建并推送：先构建并推送到私有仓库，生产端设置同一 `IMAGE_REGISTRY` 直接拉取：

```bash
docker compose build
docker compose push
```

若需要按镜像锁定具体 digest（例如 `registry.example.com/postgres@sha256:…`），可在编排文件中直接改写对应 `image:` 行，或使用私有仓库的不可变 tag（如 `v1.0.0`）配合 CI 人工评审升级。
