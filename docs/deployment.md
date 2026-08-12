# 部署与运维

Portal OSS 使用 Docker Compose 部署。仓库**不内置反向代理**：前端与后端作为独立服务直接暴露，生产环境的 HTTPS、域名与路由由部署环境（K8s Ingress、云负载均衡、外部网关）负责。

## 架构

```text
浏览器 → [部署环境的 HTTPS / 反向代理，不属于本仓库]
          ├── 前端服务（:5173，React 静态资源）
          └── 后端服务（:8000，FastAPI /api /oauth2）
后端 → PostgreSQL 16（数据）+ Redis 7（挑战/限流/待授权请求）
后端密钥卷：/app/keys（JWT 私钥 + Fernet 加密密钥）
```

## 一条命令启动（生产形态）

```bash
cp .env.example .env
# 按需修改 .env（域名、Cookie、邮件、密码等；生产配置示例见 .env.example 底部注释）
docker compose -f docker-compose.yaml --env-file .env up -d --build
```

开发与生产共用这一份 `docker-compose.yaml`：本地直接 `docker compose up -d --build`；生产按上文配置 `.env` 后再启动即可。

启动后：

- 门户：http://localhost:5173
- 示例授权网站：http://localhost:3001
- 后端健康检查：http://localhost:8000/healthz

## 首次使用

1. 在门户注册账号并激活邮箱。
2. 提升管理员：

```bash
cd backend
python -m venv .venv  # 或复用已有虚拟环境
.venv/bin/python -m scripts.make_admin <你的邮箱>
```

3. 创建演示客户端（可选，示例网站需要）：

```bash
.venv/bin/python -m scripts.seed_demo_client
```

## 环境变量

| 变量 | 说明 |
| --- | --- |
| `FRONTEND_BASE_URL` | 门户前端地址（浏览器跳转用） |
| `JWT_ISSUER` | 后端签发地址，必须与对外域名一致 |
| `CORS_ORIGINS` | 允许的前端来源（JSON 数组） |
| `SESSION_COOKIE_SECURE` | HTTPS 下必须 `true` |
| `SESSION_COOKIE_SAMESITE` | HTTPS 跨站部署建议 `none` |
| `DATABASE_URL` / `REDIS_URL` | 数据与缓存连接串 |
| `PENDING_REQUEST_STORE` / `TWOFA_STORE` / `RATE_LIMITER` | 生产用 `redis` |
| `JWT_PRIVATE_KEY_PATH` / `ENCRYPTION_KEY_PATH` | 密钥文件路径（生产指向 `/app/keys` 卷） |
| `EMAIL_BACKEND` | `console`（开发）或 SMTP 实现（生产） |
| `SMTP_HOST` / `SMTP_PORT` | SMTP 服务器地址与端口（生产必填） |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | SMTP 登录凭据（按需） |
| `SMTP_FROM` / `SMTP_FROM_NAME` | 真实发件地址与发件人名称（生产必填 `SMTP_FROM`） |
| `SMTP_USE_TLS` | 是否使用 STARTTLS（默认 `true`） |

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

## 密钥管理

- JWT 私钥与 Fernet 密钥首次启动时自动生成，写入 `backend-keys` 命名卷（容器内 `/app/keys`）。
- **必须备份该卷**：

```bash
docker run --rm -v portal_backend-keys:/keys -v "$PWD":/backup alpine \
  tar czf /backup/backend-keys.tar.gz -C /keys .
```

- 丢失 JWT 私钥：所有已签发 access token 失效，需重新部署并让用户重新登录。
- 丢失 Fernet 密钥：已加密的 TOTP 密钥无法解密，管理员需逐个重置用户 2FA。

## PostgreSQL 备份与恢复

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

建议配置定时任务（cron/云备份）并定期演练恢复。

## HTTPS 与反向代理

仓库不包含反代组件。生产上线时：

1. 在部署环境配置 TLS 与路由（例如 K8s Ingress、云负载均衡或外部网关），把域名指向前端与后端服务。
2. 更新 `.env`（参考 `.env.example` 底部的生产配置示例）：
   - `JWT_ISSUER=https://auth.example.com`
   - `FRONTEND_BASE_URL=https://portal.example.com`
   - `CORS_ORIGINS=["https://portal.example.com"]`
   - `SESSION_COOKIE_SECURE=true`
   - `SESSION_COOKIE_SAMESITE=none`
3. 重新构建并启动。

## 常见运维操作

- 查看日志：`docker compose -f docker-compose.yaml --env-file .env logs -f backend`
- 查看健康状态：`docker compose -f docker-compose.yaml --env-file .env ps`
- 升级：拉取新代码后 `up -d --build`，后端启动时会自动执行 `alembic upgrade head`
- 审计查询：管理员登录门户后调用 `GET /api/v1/admin/audit-logs`（或直接查 `audit_logs` 表）
