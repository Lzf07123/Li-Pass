# Li&Pass — 统一登录门户

一次注册，通行所有授权网站。Li&Pass 是一个基于 Python（FastAPI）和 React 的统一身份提供商（SSO），授权网站通过标准 OIDC/OAuth2 协议接入，用户使用一个账号即可登录所有被授权的网站。

## 功能特性

- 统一注册与登录：邮箱 + 密码，邮箱激活验证；注册完成自动跳转登录页，支持记住账号
- 密码强度实时显示：弱/中/强三段色条，覆盖注册、找回密码、修改密码与管理员建号
- 二次验证（2FA）：强制开启——注册验证邮箱后默认启用邮箱验证码，可升级 TOTP 认证器（含一次性恢复码），账号必须至少保留一种 2FA 方案
- 登录限流与审计：防暴力破解、关键操作审计日志、管理员重置 2FA
- 标准 OIDC 接入：授权码 + PKCE、发现文档、userinfo、JWKS
- 联邦登出：RP 发起登出（end-session）、回程登出通知（logout_token）、无回程网站的浏览器串跳漏斗
- 自动捕获会话：浏览器已有门户会话时，免输密码直接进入授权确认页
- 授权确认：首次授权必询问，可配置每次询问；同意记录复用
- 网站级访问控制：每个授权网站可独立封禁/解封账号，认证链路三层拦截
- 用户中心：资料修改、头像上传、密码修改、**更换登录邮箱（新邮箱验证码 + 当前密码复核，OpenID `sub` 标识不变）**、设备与会话管理、站内信收件箱与邮件通知开关、账号注销（手机绑定接口保留，前端暂未开放）；修改密码、2FA 开关等敏感操作支持密码二次复核（30 分钟免重复输入），注销账号必须同时输入当前密码与任意一种 2FA 验证码
- 应用广场：展示已授权网站，一键进入
- 管理后台：用户管理（邀请注册/批量邀请、批量状态/删除）、会话监控（查看在线会话与 IP 归属地，支持单个/批量/全部强制下线）、通知管理（站内信/自定义邮件）、授权网站管理（含黑名单）、站点设置（公开注册开关与 IP 归属地库更新）、系统信息（内存/磁盘/负载/服务状态）、数据统计（账号构成、登录趋势、认证方式与登录地域分布）、审计日志
- 网站自助黑名单 API：授权网站可用自己的 client_id/secret 封禁/解封账号
- 示例授权网站：本地一键演示完整登录闭环

## 技术栈

| 层次 | 技术 |
| --- | --- |
| 后端 | FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic |
| 前端 | React + Vite + TypeScript + Tailwind CSS |
| 数据 | PostgreSQL 16 + Redis 7 |
| 安全 | Argon2id、RS256 JWT、TOTP、PKCE、多层登录限流与审计、HSTS/CSP 安全头与 CSRF Origin 校验 |
| 部署 | Docker Compose + 内置 nginx 单域名网关（唯一对外入口 :80）；HTTPS 与路由由部署环境负责 |

## 项目结构

```
lipass/
├── backend/                 # FastAPI 认证服务
│   ├── app/
│   │   ├── api/             # REST API 与 OIDC 端点（routes/oidc.py）
│   │   ├── models/          # SQLAlchemy 模型
│   │   ├── schemas/         # Pydantic 校验模型
│   │   ├── security/        # 密码哈希、JWT、TOTP、限流、审计
│   │   ├── services/        # 邮件、会话、2FA、黑名单等业务服务
│   │   └── core/            # 配置、数据库、日志
│   ├── scripts/             # 运维脚本（已内置进镜像）：make_admin、demote_admin、seed_demo_client、rotate_jwt_key、download_ip2region
│   └── tests/               # 后端测试（已入库，仓库根可跑 pytest）
├── frontend/                # React SPA 门户
│   ├── src/
│   │   ├── pages/           # 登录、注册、授权确认、用户中心、应用广场、管理后台
│   │   ├── api/             # API 客户端
│   │   ├── components/      # 品牌、外壳、主题等公共组件
│   │   └── hooks/           # 自定义 Hook
│   └── __tests__/           # 前端测试（已入库，vitest）
├── examples/demo-site/      # 示例授权网站（OIDC 演示，demo profile）
├── gateway/                 # 单域名 nginx 网关（/ 前端、/api 后端、/demo 演示站）
├── scripts/                 # PostgreSQL 备份/恢复脚本
├── docs/                    # 设计文档与对接文档
├── AGENTS.md                # 项目协作手册（后续 AI Agent 开发入口）
└── docker-compose.example.yaml  # 编排示例（复制为 docker-compose.yaml 使用）
```

## 参与开发（Agent 协作）

项目采用「设计先行 → 计划拆解 → TDD 实现 → 全量验证 → 记录」的开发方法。新会话的 AI Agent 请先读 [AGENTS.md](./AGENTS.md)（硬性规则、架构地图、验证命令与工作流）；spec/plan 文档规范见 [docs/superpowers/README.md](./docs/superpowers/README.md)。

## 快速开始（开发环境）

全部五个里程碑（项目骨架与账号体系、OIDC 核心、用户中心与访问控制、2FA 与安全加固、生产部署与文档）已完成。最快捷的方式是一键启动全栈（含前端、后端与基础设施）：

```bash
cp docker-compose.example.yaml docker-compose.yaml
docker compose --profile bundle up -d --build
```

启动后通过单域名网关访问 http://localhost （前端 `/`、后端 API `/api`、OIDC `/oauth2`、演示站 `/demo`）。前端与后端容器**不向宿主机开放端口**，唯一对外入口是网关（nginx）的 80 端口。健康检查：`GET /healthz`（存活）、`GET /readyz`（就绪）。开发环境邮件验证码默认打印到后端容器日志（`docker compose logs backend | grep "code="`）。

### 本地开发热更新（改动即时生效）

容器化单域名栈默认按生产形态构建，改代码需要重新 `--build`。本地开发可叠加
`docker-compose.dev.yaml` 覆盖文件：保持与生产相同的网关拓扑，同时获得前后端热更新。

```bash
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml \
  --profile bundle up -d --build
```

- 后端：`backend/app/**` 改动由 uvicorn `--reload`（WatchFiles）自动重启；数据库迁移文件改动不触发重载，需 `docker compose -f docker-compose.yaml -f docker-compose.dev.yaml restart backend`（启动时自动执行 `alembic upgrade head`）。
- 前端：`frontend/src/**` 改动由 Vite HMR 即时热替换；网关透传 WebSocket 升级请求（`gateway/nginx.conf.template` 已支持 Upgrade），容器内源码挂载并开启轮询监听（`VITE_WATCH_POLLING=true`），规避 macOS/Docker Desktop 下 bind mount 的 inotify 事件丢失。
- 依赖（`requirements.txt` / `package*.json`）、compose、`.env` 或网关模板改动不属于热更新范围：重新 `up -d --build`（前端依赖变化时追加 `--force-recreate frontend`）。

开发验证码同样打印到后端日志：

```bash
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml \
  logs -f backend | grep 'code='
```

`bundle` profile 会一并启动编排内的 PostgreSQL 与 Redis。如果改用远程 PostgreSQL/Redis，只需在 `.env` 中配置 `DATABASE_URL` / `REDIS_URL`，并去掉 `--profile bundle`（编排内不再启动这两个服务）：

```bash
docker compose up -d --build
```

如需在宿主机上分别运行各服务，按以下步骤执行：

> 以下仅适用于不使用 Docker 的宿主机开发；容器部署请使用上方的 compose 方式，
> 前端/后端端口不映射到宿主机，唯一对外入口是 gateway（nginx）。

1. 启动基础设施：

   ```bash
   docker compose --profile bundle up -d postgres redis
   ```

2. 启动后端（Python 3.11+）：

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/simple
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
   pip install -r requirements.txt -i https://mirrors.ustc.edu.cn/pypi/simple
   export PORTAL_ISSUER=http://localhost:8000 PORTAL_CLIENT_ID=demo-site \
     DEMO_REDIRECT_URI=http://localhost:3001/callback
   python app.py
   ```

开发环境邮件验证码默认打印到后端控制台日志，无需真实邮件服务。

### 生产形态启动

```bash
cp docker-compose.example.yaml docker-compose.yaml
cp .env.example .env
docker compose -f docker-compose.yaml --profile bundle --env-file .env up -d --build
```

> 使用远程 PostgreSQL/Redis 时去掉 `--profile bundle`，并在 `.env` 中设置 `DATABASE_URL` / `REDIS_URL`。

### 生产级热更新（零停机更新）

默认生产形态不可变（代码烧进镜像，改动需 `up -d --build`）。需要零停机更新时，以热更新
覆盖文件启动（一次性切换形态，会重建 backend/frontend 容器）：

```bash
docker compose -f docker-compose.yaml -f docker-compose.hot.yaml \
  --profile bundle up -d --build
```

- backend：代码放入 `backend-code` 卷、`HOT_UVICORN_WORKERS` 默认 2；更新 = 写卷 + SIGHUP，
  uvicorn 逐个 worker 优雅回收，在途请求不中断；要求 `PENDING_REQUEST_STORE` /
  `TWOFA_STORE` / `RATE_LIMITER` 均为 `redis`。
- frontend：产物放入 `frontend-web` 卷；`scripts/hot_update.sh frontend` 会在一次性
  node 容器内自动 `npm ci`（package-lock 哈希增量缓存）+ `npm run build`（`VITE_*`
  自动从 `.env` 注入），再原地换装 + `nginx -s reload`；`--skip-build` 可复用已有 `dist`。
- gateway：模板重新 envsubst + `nginx -s reload`。

更新、快照、SHA256 校验与回滚统一走 `scripts/hot_update.sh`（用法见
[部署文档 §生产级热更新](docs/deployment.md)）。依赖、Dockerfile、入口命令、环境变量、
compose 拓扑以及 `alembic`/`scripts`/`ip2region` 目录的变更不属于热更新范围，仍按
`up -d --build` 重建。

详细部署、密钥备份与 HTTPS 说明见 [docs/deployment.md](docs/deployment.md)。

示例授权网站（OIDC 演示，端口 3001）：

```bash
docker compose --profile bundle --profile demo up -d --build
docker compose exec backend python -m scripts.seed_demo_client
```

打开 http://localhost/demo/ 点击“通过门户登录”，即可体验从第三方网站跳转到门户授权确认并登录的完整闭环。

> 示例授权网站位于 `demo` profile，默认 `docker compose up -d` 不会启动它，生产栈不会携带演示应用。

## 演示数据

- `docker compose exec backend python -m scripts.seed_demo_client`：创建示例授权网站客户端（`demo-site`，公开客户端）
- `docker compose exec backend python -m scripts.make_admin <邮箱>`：把已注册用户提升为管理员（可管理应用与黑名单、查看审计日志）
- `docker compose exec backend python -m scripts.demote_admin <邮箱>`：把管理员降级为普通用户（拒绝降级最后一名管理员）

## 文档

- 设计文档：[docs/superpowers/specs/2026-08-12-unified-login-portal-design.md](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)
- 部署与运维：[docs/deployment.md](docs/deployment.md)
- OIDC 对接指南（含对接方必选/可选接口契约与接入验收清单）：[docs/oidc-integration.md](docs/oidc-integration.md)
- 更新日志：[CHANGELOG.md](CHANGELOG.md)

## 设计文档

完整设计见 [docs/superpowers/specs/2026-08-12-unified-login-portal-design.md](docs/superpowers/specs/2026-08-12-unified-login-portal-design.md)。

## 实施路线

- ✅ 里程碑 1：项目骨架 + 基础账号体系
- ✅ 里程碑 2：OIDC 核心流程
- ✅ 里程碑 3：用户中心 + 网站级访问控制
- ✅ 里程碑 4：2FA + 安全加固
- ✅ 里程碑 5：生产部署 + 对接文档

## 开源协议

本项目采用 [Apache License 2.0](LICENSE) 发布。你可以自由使用、修改、分发与商用，同时保留版权与许可声明。

第三方组件说明：`backend/ip2region/` 为 ip2region v3.17.0 的官方 Python 绑定源码（Apache-2.0），其许可文件随源码保留在 [backend/ip2region/LICENSE](backend/ip2region/LICENSE)，供本地开发与测试使用；Docker 镜像在构建时按固定 tag + SHA256 校验从上游拉取绑定源码与 xdb 数据（见 `backend/scripts/download_ip2region.py`）。
