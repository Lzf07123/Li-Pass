# Li&Pass 项目协作手册

> 本文件是给后续 AI Agent（Codex 等）的“项目宪法”。**新会话必须先完整读完本文件再动手。**
> 它定义：事实来源、硬性规则、标准工作流、验证口径与常见坑。人类开发者同样适用。

## 一、项目是什么

Li&Pass 是自研的统一身份提供商（SSO / OIDC IdP）：一次注册、通行所有接入网站。后端 FastAPI + PostgreSQL 16 + Redis 7，前端 React + Vite + TypeScript + Tailwind CSS 4，经内置 nginx 单域名网关部署。详见 [README.md](./README.md)。

**这是安全产品**：任何改动都不得降低认证强度、破坏 OIDC 合规、绕过限流/审计或泄露用户数据。安全回归的代价高于功能进度。

## 二、事实来源（动手前按顺序读）

| 内容 | 位置 |
| --- | --- |
| 产品全貌、目录结构、快速开始 | [README.md](./README.md) |
| 最近改动与历史决策 | [CHANGELOG.md](./CHANGELOG.md)（先看顶部「未发布（开发中）」）、`git log --oneline -20` |
| 部署、环境变量、迁移、备份、上线清单 | [docs/deployment.md](./docs/deployment.md) |
| OIDC 对外契约（端点/令牌/登出/安全要求） | [docs/oidc-integration.md](./docs/oidc-integration.md) |
| 设计与实施文档规范 | [docs/superpowers/README.md](./docs/superpowers/README.md) |
| 视觉与品牌规范 | [design-system/lipass/MASTER.md](./design-system/lipass/MASTER.md)、[BRAND.md](./design-system/lipass/BRAND.md) |

**文档与代码冲突时：代码是运行事实，文档是意图。**先核对差异，再决定改哪边；改代码必须同步文档（见「收尾」）。

## 三、架构地图

```text
backend/                 FastAPI 认证服务（Python 3.12）
├── app/
│   ├── api/routes/      REST 与 OIDC 路由（/api/v1/*、/oauth2/*）
│   ├── models/          SQLAlchemy 2.0 模型
│   ├── schemas/         Pydantic v2 校验模型
│   ├── security/        密码哈希/JWT/TOTP/限流/审计
│   ├── services/        邮件、会话、2FA、黑名单、联邦登出、geoip 等业务
│   └── core/            config.py / db.py / redis.py
├── alembic/versions/    数据库迁移
├── data/ip2region 与 ip2region/   离线 IP 库数据与绑定（vendored，SHA256 信任清单）
├── scripts/             运维脚本（make_admin、demote_admin、seed_demo_client、rotate_jwt_key、download_ip2region）
└── tests/               后端测试（已入库，仓库根可直接跑）

frontend/                React SPA 门户（Node >=22.14）
├── src/pages/           登录/注册/授权确认/用户中心/应用广场/管理后台
├── src/api/             API 客户端
├── src/components/      公共组件（PillTabs、ScrollTabs、MagicBento、ChinaMap 等）
├── src/hooks/ src/lib/  自定义 Hook 与工具
├── src/index.css        Tailwind 4 @theme 令牌（视觉事实来源）
└── src/__tests__/       前端测试（vitest）

gateway/                 单域名 nginx 网关：/ → 前端、/api + /oauth2 → 后端、/demo → 演示站；支持 Upgrade 透传（Vite HMR）
examples/demo-site/      示例 OIDC 接入站（Flask）
scripts/                 PostgreSQL 备份/恢复（backup-db/restore-db）与生产零停机热更新（hot_update）
docs/                    部署、对接、设计规格与实施计划
docker-compose.example.yaml  编排示例（复制为 docker-compose.yaml 使用，后者已 gitignore）：gateway + frontend + backend + postgres + redis（profile: bundle）、demo-site（profile: demo）
docker-compose.dev.yaml  本地开发热更新覆盖文件（Vite HMR + uvicorn --reload，仅本地）
docker-compose.hot.yaml  生产级零停机热更新覆盖文件（backend-code/frontend-web 卷 + SIGHUP worker 回收）
```

关键事实：**唯一对外入口是 gateway 的 :80**；前端/后端容器不向宿主机映射端口，生产 HTTPS 由部署环境负责。API 前缀 `/api/v1`；OIDC 在 `/oauth2/*` 与 `/.well-known/openid-configuration`。

## 四、硬性规则

1. **秘密不入库**：`.env`、`*.pem`、`*.key` 已被 gitignore。配置变更只改 `.env.example`，并同步 [docs/deployment.md](./docs/deployment.md) 的环境变量表。
2. **安全不降级**：涉及登录、会话、OIDC、令牌、密钥、限流的改动必须保持现有防护与审计覆盖。改 OIDC 契约前先读 [docs/oidc-integration.md](./docs/oidc-integration.md)。
3. **破坏性变更必须可迁移**：进 CHANGELOG「破坏性变更」分区，写明旧→新行为、兼容窗口与迁移步骤。
4. **数据库变更必须写 Alembic 迁移**，并在真实 PostgreSQL 上验证 upgrade 与 downgrade 往返。
5. **UI 改动先读设计规范**：MASTER.md + BRAND.md；令牌以 `frontend/src/index.css` 为准；动效尊重 `prefers-reduced-motion`（项目惯例）。
6. **命名**：品牌显示名 `Li&Pass`；技术标识统一 `lipass`（Cookie、kid、acr、目录、卷名）。不新增 `portal` 标识。
7. **完成 = 验证 + 文档**：声称完成前必须给出验证输出；功能合并前更新 CHANGELOG 与相关文档。
8. **遵循既有分层**：新增路由/服务/模型放入对应目录；不在 `routes/*` 里堆业务逻辑。

## 五、标准工作流（每个功能走一遍）

1. **调查**：按第二节读事实来源；搜 `docs/superpowers/specs/` 是否有历史设计；`git branch -a` 与 CHANGELOG 顶部确认没人正在做同一件事。
2. **设计（非平凡改动必做）**：写 `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`——目标、现状、方案取舍、接口/数据模型、安全影响、UI（引用设计系统）、验收标准。规范见 [docs/superpowers/README.md](./docs/superpowers/README.md)。
3. **计划（多步任务必做）**：写 `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`，按 Task 拆分；每个 Task 有精确文件、接口（Consumes/Produces）、可独立验证的交付物与 checkbox 步骤；TDD。
4. **隔离实现**：`git worktree add .worktrees/<topic> -b codex/<topic>`（或直接开分支）；每个 Task：写失败测试 → 验证红 → 最小实现 → 验证绿 → 独立提交。多任务可派子 agent 逐 Task 实现并两段评审。
5. **全量验证**：跑第六节的命令；涉及编排/迁移的要真机冒烟。
6. **收尾**：更新 [CHANGELOG.md](./CHANGELOG.md) 对应分区；同步 README/deployment/oidc-integration；`docs:` 提交；合并 main。

## 六、验证命令

后端（CI 在 `backend/` 目录、Python 3.12 下执行；本地需先激活虚拟环境或装依赖）：

```bash
cd backend
python -m pytest -q                                # 全量
python -m pytest tests/test_x.py::test_y -v       # 单个
alembic upgrade head && alembic downgrade -1      # 迁移往返（真实 PostgreSQL）
```

前端（Node 22.14，CI 顺序如下）：

```bash
cd frontend
npx tsc -b && npm run lint && npm test && npm run build
```

编排冒烟：

```bash
docker compose --profile bundle config -q         # 校验基础编排
docker compose -f docker-compose.yaml -f docker-compose.dev.yaml --profile bundle config -q   # 本地热更新覆盖
docker compose -f docker-compose.yaml -f docker-compose.hot.yaml --profile bundle config -q   # 生产热更新覆盖
docker compose --profile bundle up -d --build     # 启动（含 postgres/redis）
docker compose logs backend | grep 'code='        # 开发环境邮件验证码
curl -fsS http://localhost/healthz http://localhost/readyz
bash -n scripts/hot_update.sh                     # 热更新脚本语法
bash scripts/hot_update.sh --dry-run status       # 只读预览（生产热更新形态）
```

首次使用前先 `cp docker-compose.example.yaml docker-compose.yaml`（本机版不提交，可按环境就地修改）。

依赖安全（项目要求清零）：后端 `pip-audit`，前端 `npm audit`。

> CI 定义见 [.github/workflows/ci.yml](./.github/workflows/ci.yml)。仓库根 `pytest.ini` 已配置 `testpaths=backend/tests`、`pythonpath=backend`，依赖装好后也可从根目录直接 `python -m pytest`。

## 七、提交与分支

- 分支：`codex/<topic>`（kebab-case），完成后合并回 `main`（保留 merge 记录）。
- 提交消息：`<type>: <中文简述>`；type 用 `feat`/`fix`/`perf`/`docs`/`test`/`refactor`/`chore`。每个 Task 独立提交。
- CHANGELOG 分区：破坏性变更 / 功能 / 安全加固 / 行为变更 / 缺陷修复 / 运维工具。

## 八、常见坑（来自 CHANGELOG 历史教训）

- **后端 `.env` 路径固定**：Settings 相对 `backend/app/core/config.py` 解析为 `backend/.env`，与工作目录无关；别在仓库根放干扰测试的 `.env`。
- **Alembic downgrade**：PostgreSQL 上必须给外键命名，否则无法生成 `DROP CONSTRAINT`；新时间戳列用 `DateTime(timezone=True)`；新 JSON 列给默认值。
- **gateway proxy_pass**：带变量时 URI 部分会被整体替换，子路径要用 `rewrite` 显式剥离前缀再转发。
- **starlette >=1.6**：413 常量已更名为 `HTTP_413_REQUEST_ENTITY_TOO_LARGE`。
- **ip2region**：数据与绑定是 vendored 的，升级先 `python scripts/download_ip2region.py --data-dir data/ip2region --binding-dir ip2region` 再提交；运行期更新走 `app/services/ip2region_pins.py` 的 SHA256 信任清单。
- **镜像源**：Docker 构建默认国内 APT/PIP/npm 镜像（构建参数可切官方源），CI 用官方源；本地 npm 走 `.npmrc` 的 npmmirror。
- **前端 CSP**：生产 `style-src 'self'`（无 `unsafe-inline`），动效必须尊重 `prefers-reduced-motion`。
- **SQLite 测试夹具 ≠ PostgreSQL**：conftest 用 SQLite 内存库；外键、JSON、时区语义差异要靠真实 PostgreSQL 验证。
