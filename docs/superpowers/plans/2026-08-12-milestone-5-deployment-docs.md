# 里程碑 5：生产部署与对接文档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 提供可一条命令启动的生产形态部署（无内置反代、密钥持久卷、健康检查）与完整的 OIDC 对接文档、部署运维文档。

**Architecture:** 新增 `docker-compose.prod.yml`（frontend/backend/demo-site/postgres/redis，含健康检查与 backend 密钥卷），环境变量统一由 `.env.prod` 注入；新增 `docs/deployment.md`（启动、环境变量、密钥、备份恢复、HTTPS 说明）与 `docs/oidc-integration.md`（端点、发现文档、Python/Node 示例、错误与 acr）；README 汇总。

**Tech Stack:** 沿用现有镜像与 Compose；无新增运行时依赖。

## Global Constraints

- 仓库内不内置反向代理；生产 HTTPS/路由由部署环境负责，文档明确说明。
- 生产环境变量经 `.env.prod` 注入；JWT 私钥与加密密钥必须持久化（backend 密钥卷），绝不随容器重建丢失。
- 健康检查：backend 用 `/healthz`；postgres/redis 用官方检查；frontend/demo-site 用 HTTP 探活。
- 文档包含：新机器一条命令启动、密钥备份与恢复、PostgreSQL 备份/恢复、OIDC 接入步骤与示例代码。
- 本里程碑在当前会话内联执行（控制器实现并验证）。

---

### Task 1: 生产 Compose 与环境示例

**Files:**
- Create: `docker-compose.prod.yml`
- Create: `.env.prod.example`

**Interfaces:**
- Produces: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build` 可启动全套；backend 密钥写入命名卷。

- [ ] **Step 1: 编写 `.env.prod.example`**

```text
# 域名与来源
FRONTEND_BASE_URL=http://localhost:5173
JWT_ISSUER=http://localhost:8000
CORS_ORIGINS=["http://localhost:5173"]

# 会话 Cookie：生产 HTTPS 下必须 true / none
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax

# 数据与缓存
DATABASE_URL=postgresql+psycopg://portal:portal@postgres:5432/portal
REDIS_URL=redis://redis:6379/0
POSTGRES_USER=portal
POSTGRES_PASSWORD=portal
POSTGRES_DB=portal

# 存储后端
PENDING_REQUEST_STORE=redis
TWOFA_STORE=redis
RATE_LIMITER=redis

# 密钥路径（容器内 /app/keys 命名卷持久化）
JWT_PRIVATE_KEY_PATH=/app/keys/jwt_private.pem
ENCRYPTION_KEY_PATH=/app/keys/encryption.key

# 邮件（生产接 SMTP；本示例保持控制台）
EMAIL_BACKEND=console
```

- [ ] **Step 2: 编写 `docker-compose.prod.yml`**

要点：

- 复用 `docker-compose.yml` 的四个服务定义，改为 `build` + `env_file: .env.prod`。
- backend 增加卷 `backend-keys:/app/keys`，并保留 `alembic upgrade head && uvicorn ...` 启动命令与 `/healthz` 健康检查。
- frontend/demo-site 增加 HTTP 健康检查（`wget -qO- http://localhost:端口/` 或等价探活）。
- 不包含任何反代组件。
- 服务端口与开发版一致（5173/8000/3001/5432/6379），命名卷带 `-prod` 后缀避免与开发栈冲突。

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env_file: .env.prod
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports: ["5432:5432"]
    volumes: ["postgres-data-prod:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["redis-data-prod:/data"]

  backend:
    build: ./backend
    env_file: .env.prod
    ports: ["8000:8000"]
    volumes: ["backend-keys:/app/keys"]
    depends_on:
      postgres: { condition: service_healthy }
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:8000/healthz >/dev/null || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 10

  frontend:
    build:
      context: ./frontend
      args: { VITE_API_BASE_URL: "http://localhost:8000" }
    ports: ["5173:5173"]
    depends_on: [backend]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:5173/ >/dev/null || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 10

  demo-site:
    build: ./examples/demo-site
    environment:
      PORTAL_ISSUER: ${FRONTEND_BASE_URL:-http://localhost:8000}
      PORTAL_API_BASE: http://backend:8000
      PORTAL_CLIENT_ID: demo-site
    ports: ["3001:3001"]
    depends_on: [backend]
    healthcheck:
      test: ["CMD-SHELL", "wget -qO- http://localhost:3001/ >/dev/null || exit 1"]
      interval: 10s
      timeout: 3s
      retries: 10

volumes:
  postgres-data-prod:
  redis-data-prod:
  backend-keys:
```

注意：demo-site 的 `PORTAL_ISSUER` 用于浏览器跳转到门户后端，取 `JWT_ISSUER`（不是 `FRONTEND_BASE_URL`）；示例默认 localhost。

- [ ] **Step 3: 校验配置**

Run: `docker compose -f docker-compose.prod.yml --env-file .env.prod config -q`

Expected: 无错误输出。

- [ ] **Step 4: 提交**

```bash
git add docker-compose.prod.yml .env.prod.example
git commit -m "feat: 生产 Compose 与环境示例（密钥卷/健康检查）"
```

---

### Task 2: 部署文档

**Files:**
- Create: `docs/deployment.md`

**内容要点：**

- 架构图（浏览器 → 部署环境 HTTPS/反代 → frontend/backend；backend → postgres/redis；密钥卷）
- 新机器一条命令启动：

```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- 首次使用：注册账号 → `cd backend && .venv/bin/python -m scripts.make_admin <email>`（或用容器内方式）→ `python -m scripts.seed_demo_client` 生成演示客户端。
- 环境变量说明表（域名、Cookie、邮件、存储后端、密钥路径）。
- 密钥管理：JWT 私钥与 Fernet 密钥在 `backend-keys` 卷，备份该卷；丢失私钥会导致令牌失效、加密的 TOTP 密钥无法解密（需管理员重置）。
- PostgreSQL 备份：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod exec postgres \
  pg_dump -U portal portal | gzip > portal-$(date +%Y%m%d-%H%M%S).sql.gz
```

- 恢复：`gunzip -c backup.sql.gz | docker compose ... exec -T postgres psql -U portal portal`。
- HTTPS/反代说明：仓库不内置反代；生产必须由 K8s Ingress/云负载均衡/网关终止 TLS，并将 `SESSION_COOKIE_SECURE=true`、`SESSION_COOKIE_SAMESITE=none`、`JWT_ISSUER`/`FRONTEND_BASE_URL`/`CORS_ORIGINS` 改为真实域名。

完成并提交：

```bash
git add docs/deployment.md
git commit -m "docs: 部署与运维文档"
```

---

### Task 3: OIDC 对接文档

**Files:**
- Create: `docs/oidc-integration.md`

**内容要点：**

- 发现文档：`GET {issuer}/.well-known/openid-configuration`，返回 issuer/authorize/token/userinfo/jwks、支持的 scope 与 PKCE S256。
- 授权码 + PKCE 步骤（公开客户端）：
  1. 生成 verifier 与 challenge（S256）
  2. 跳转 authorize（`response_type=code&client_id&redirect_uri&scope=openid profile email&state&nonce&code_challenge&code_challenge_method=S256`）
  3. 用户登录/授权后回跳 `redirect_uri?code=...&state=...`
  4. token 端点换令牌（`grant_type=authorization_code&code&redirect_uri&client_id&code_verifier`，机密客户端加 `client_secret`）
  5. `GET /oauth2/userinfo` 带 `Authorization: Bearer`
- Python 示例（requests，与 `examples/demo-site/app.py` 一致）与 Node 示例（fetch）。
- 机密客户端说明：`client_secret` 只显示一次；可调 `/oauth2/client/blocks` 自助黑名单（Basic 鉴权）。
- 错误码：`invalid_request/invalid_scope/unauthorized_client/invalid_redirect_uri/access_denied`（含 `error_description=account_blocked`）、`invalid_grant`、`invalid_client`、`invalid_token`。
- `acr` 声明：`urn:portal-oss:acr:1fa` / `urn:portal-oss:acr:2fa`，需要强认证的网站可据此要求。

完成并提交：

```bash
git add docs/oidc-integration.md
git commit -m "docs: OIDC 对接文档"
```

---

### Task 4: README 与演示数据

**Files:**
- Modify: `README.md`

**改动：**

- 快速开始增加“生产形态启动”小节（指向 `docs/deployment.md`）。
- 文档索引：`docs/deployment.md`、`docs/oidc-integration.md`、设计文档与各里程碑计划。
- 演示数据说明：`seed_demo_client` 创建 `demo-site` 客户端；`make_admin` 提升管理员；注册流程生成演示用户。

提交：

```bash
git add README.md
git commit -m "docs: README 生产启动与文档索引"
```

---

### Task 5: 生产栈启动与 E2E 收尾

- [ ] **Step 1: 停开发栈、启动生产栈**

```bash
docker compose -p milestone-2-oidc-core down
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build
```

- [ ] **Step 2: 端到端验证（curl，localhost）**

1. `/healthz` 200；frontend :5173 200；demo-site :3001 200。
2. 注册→激活→登录→示例网站授权闭环（复用里程碑 2/3 的脚本思路）。
3. 种子 `demo-site` 客户端（`cd backend && .venv/bin/python -m scripts.seed_demo_client`）。
4. 可选：开启邮箱 2FA → 两步登录冒烟。

- [ ] **Step 3: 收尾提交**

确认 `git status` 干净、文档齐全，必要时补提交。

---

## 里程碑 5 完成标准

- 新机器按文档一条命令启动生产栈，健康检查通过。
- JWT 私钥与加密密钥持久化在命名卷，文档说明备份/恢复。
- OIDC 对接文档完整（发现、授权码+PKCE、token/userinfo、示例、错误、acr）。
- 生产栈上注册→登录→示例网站授权闭环通过；工作区干净。
