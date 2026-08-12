# Portal OSS — 统一登录门户

一次注册，通行所有授权网站。Portal OSS 是一个基于 Python（FastAPI）和 React 的统一身份提供商（SSO），授权网站通过标准 OIDC/OAuth2 协议接入，用户使用一个账号即可登录所有被授权的网站。

## 功能特性

- 统一注册与登录：邮箱 + 密码，邮箱激活验证
- 二次验证（2FA）：邮箱验证码或 TOTP 认证器，含一次性恢复码
- 登录限流与审计：防暴力破解、关键操作审计日志、管理员重置 2FA
- 标准 OIDC 接入：授权码 + PKCE、发现文档、userinfo、JWKS
- 自动捕获会话：浏览器已有门户会话时，免输密码直接进入授权确认页
- 授权确认：首次授权必询问，可配置每次询问；同意记录复用
- 网站级访问控制：每个授权网站可独立封禁/解封账号，认证链路三层拦截
- 用户中心：资料修改、手机绑定、密码修改、设备与会话管理
- 应用广场：展示已授权网站，一键进入
- 管理后台：用户管理、授权网站管理、黑名单管理、审计日志
- 网站自助黑名单 API：授权网站可用自己的 client_id/secret 封禁/解封账号
- 示例授权网站：本地一键演示完整登录闭环

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic |
| 前端 | React + Vite + TypeScript + Tailwind CSS |
| 数据 | PostgreSQL 16 + Redis 7 |
| 安全 | Argon2id、RS256 JWT、TOTP、PKCE、限流与审计 |
| 部署 | Docker Compose（不含反向代理）；HTTPS 与路由由部署环境负责 |

## 项目结构

```
portal-oss/
├── backend/                 # FastAPI 认证服务
│   ├── app/
│   │   ├── api/             # REST API：用户中心、管理后台、授权确认
│   │   ├── oidc/            # OIDC Provider
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 校验模型
│   │   ├── security/        # 密码哈希、JWT、TOTP、限流、审计
│   │   ├── services/        # 邮件、会话、2FA、黑名单等业务服务
│   │   └── core/            # 配置、数据库、日志
│   └── tests/
├── frontend/                # React SPA 门户
│   ├── src/
│   │   ├── pages/           # 登录、注册、授权确认、用户中心、应用广场
│   │   ├── api/             # API 客户端
│   │   └── components/
│   └── tests/
├── examples/demo-site/      # 示例授权网站
├── docs/                    # 设计文档与对接文档
└── docker-compose.yaml      # frontend + backend + postgres + redis（不含反向代理）
```

## 快速开始（开发环境）

里程碑 1（项目骨架 + 基础账号体系）已完成。最快捷的方式是一键启动全栈（含前端、后端与基础设施）：

```bash
docker compose up -d --build
```

启动后前端位于 http://localhost:5173 ，后端 API 位于 http://localhost:8000 （健康检查 `GET /healthz`）。开发环境邮件验证码默认打印到后端容器日志（`docker compose logs backend | grep "code="`）。

如需在宿主机上分别运行各服务，按以下步骤执行：

1. 启动基础设施：

   ```bash
   docker compose up -d postgres redis
   ```

2. 启动后端（Python 3.11+）：

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

3. 启动前端（通过 `VITE_API_BASE_URL` 直连后端，不内置代理）：

   ```bash
   cd frontend
   cp .env.example .env
   export VITE_API_BASE_URL=http://localhost:8000
   npm install
   npm run dev
   ```

4. 启动示例授权网站：

   ```bash
   cd examples/demo-site
   pip install -r requirements.txt
   export PORTAL_ISSUER=http://localhost:8000 PORTAL_CLIENT_ID=demo-site \
     DEMO_REDIRECT_URI=http://localhost:3001/callback
   python app.py
   ```

开发环境邮件验证码默认打印到后端控制台（或本地 Mailpit），无需真实邮件服务。

### 生产形态启动

```bash
cp .env.example .env
docker compose -f docker-compose.prod.yaml --env-file .env up -d --build
```

详细部署、密钥备份与 HTTPS 说明见 [docs/deployment.md](docs/deployment.md)。

示例授权网站（OIDC 演示，端口 3001）：

```bash
docker compose up -d --build demo-site
cd backend && .venv/bin/python -m scripts.seed_demo_client
```

打开 http://localhost:3001 点击“通过门户登录”，即可体验从第三方网站跳转到门户授权确认并登录的完整闭环。

## 演示数据

- `cd backend && .venv/bin/python -m scripts.seed_demo_client`：创建示例授权网站客户端（`demo-site`，公开客户端）
- `cd backend && .venv/bin/python -m scripts.make_admin <邮箱>`：把已注册用户提升为管理员（可管理应用与黑名单、查看审计日志）

## 文档

- 设计文档：[docs/superpowers/specs/2026-08-12-unified-login-portal-design.md](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)
- 部署与运维：[docs/deployment.md](docs/deployment.md)
- OIDC 对接指南：[docs/oidc-integration.md](docs/oidc-integration.md)

## 设计文档

完整设计见 [docs/superpowers/specs/2026-08-12-unified-login-portal-design.md](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)。

## 实施路线

- 里程碑 1：项目骨架 + 基础账号体系
- 里程碑 2：OIDC 核心流程
- 里程碑 3：用户中心 + 网站级访问控制
- 里程碑 4：2FA + 安全加固
- 里程碑 5：生产部署 + 对接文档
