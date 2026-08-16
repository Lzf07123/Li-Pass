# 生产级热更新（零停机更新）设计

- 日期：2026-08-17
- 状态：已实现

## 1. 目标

在不降级安全与可用性的前提下，让单节点 compose 部署支持**生产级热更新**：

1. 前端：静态产物原地换装，秒级生效、不重启容器、不中断访问；
2. 后端：Python 代码更新经 uvicorn 优雅回收 worker，多 worker 下不中断在途请求；
3. 网关：配置变更用 `nginx -s reload` 平滑生效；
4. 全程可校验（SHA256）、可回滚、可审计，并有明确的不适用边界。

**明确排除**开发态热重载进入生产：不使用 `--reload` 文件监听，不使用 Vite dev
server 托管生产流量（见风险章节）。本方案是零停机更新的生产等价物。

## 2. 现状与约束

- 后端镜像 `CMD`：`alembic upgrade head && uvicorn ... --workers ${UVICORN_WORKERS:-1} --limit-max-requests 10000`；
  多 worker 由 uvicorn 内置 supervisor 管理，**SIGHUP → `restart_all()` 逐个 worker 依次重启**
  （终止一个、拉起一个，其余 worker 继续服务），因此 `UVICORN_WORKERS≥2` 时 SIGHUP 即为
  零停机的代码热回收（已验证 `uvicorn/supervisors/multiprocess.py`）。
- 生产校验（`app/core/config.py`）强制：真实域名/HTTPS/绝对密钥路径/redis 存储/SMTP；
  `PENDING_REQUEST_STORE/TWOFA_STORE/RATE_LIMITER` 生产必须是 redis，worker 重启不丢进行中的
  2FA 挑战、限流计数与待授权请求。
- 前端为 nginx 托管静态产物（`open_file_cache` 打开），`index.html` 已 `no-cache`；
  带内容 hash 的资产可长缓存，原地换装天然兼容多版本并存。
- compose 唯一对外入口是 gateway `:80`；backend/frontend 不发布宿主机端口。
- nginx `1.27.5`（编排镜像 `nginx:1.27-alpine` 实测）：无需动态上游解析，本方案不重启网关
  即可热更新 frontend/backend 内容（backend 代码在容器内替换，服务端口与 IP 不变）。
- 迁移约束（项目硬规则）：破坏性数据库变更必须可迁移，热更新期间旧代码可能短暂与新 schema
  并存，迁移必须向前兼容（expand/contract 顺序）。

## 3. 方案与取舍

### 3.1 启用方式：热更新编排覆盖文件（默认生产仍不可变）

新增 `docker-compose.hot.yaml`（叠加在 `docker-compose.yaml` 上）：

- `backend-code:/app/app`：后端代码改为命名卷承载（首挂载时 Docker 自动以镜像内容播种）；
  `UVICORN_WORKERS` 默认提升为 2；
- `frontend-web:/usr/share/nginx/html`：前端产物改为命名卷承载（同样自动播种）。

取舍：
- 默认编排保持「代码烧进镜像」的不可变形态；只有显式以热更新形态启动的栈才挂这两个卷，
  把可写代码面的引入限定为运维的显式决定。
- 首次切换形态需要重建这两个容器（一次性）；之后进入热更新模式。

### 3.2 前端热换装

```text
本地 npm run build（产出 frontend/dist）
  → 快照当前卷内容到宿主 deploy-backups/<ts>/frontend-html
  → docker cp 新 dist 进入 frontend-web 卷（先 assets/，再根文件，最后 index.html）
  → docker compose exec frontend nginx -s reload（刷新 open_file_cache）
```

取舍：
- 带 hash 的资产文件名不同，新老文件可短暂并存；`index.html` 最后落地 + no-cache，
  用户下一请求即拿新入口，无版本混用。
- 不做「整目录原子换名」：nginx 的 root 需要 stable 路径，symlink 换名方案复杂化
  open_file_cache 与 CSP/安全头配置，收益有限。

### 3.3 后端零停机回收

```text
校验前置条件（已挂 backend-code、UVICORN_WORKERS≥2、存储为 redis、后端 healthy）
  → 快照当前 /app/app 到宿主 deploy-backups/<ts>/backend-app
  → （可选）docker compose exec backend alembic upgrade head
  → docker cp backend/app/. backend:/app/app/
  → docker compose kill -s HUP backend
  → 等待 health=healthy，并核对日志出现 "Received SIGHUP, restarting processes."
```

取舍：
- 依赖 uvicorn supervisor 的 `restart_all` 语义：≥2 workers 时任何时刻只有至多一个 worker
  在重启，其余继续接流量；SIGTERM 下 worker 优雅排空在途请求。
- 代码用 `docker cp` 换入卷：无镜像重建、无容器重启、无端口/IP 变化，网关无需感知。
- 迁移先行且必须向后兼容；失败时脚本停止并提示人工处理（代码尚未替换）。
- 不适用（需整栈重建）：依赖变更、Dockerfile/入口命令、环境变量与 compose 拓扑变更、
  `alembic`/`scripts`/`ip2region` 目录变更（这些仍走 `up -d --build`，由 stop_grace_period
  与健康检查排空）。

### 3.4 网关配置热更新

```text
docker compose exec gateway /docker-entrypoint.d/20-envsubst-on-templates.sh
docker compose exec gateway nginx -s reload
```

模板改动后重新 envsubst 再 reload，避免「改了模板文件但 conf.d 还是旧内容」。

### 3.5 脚本与安全

`scripts/hot_update.sh`：

- 子命令：`frontend | backend | gateway | all`；选项 `--dry-run`、`--rollback <ts>`、
  `--skip-migrations`；
- 所有写操作前做宿主侧快照（含 SHA256 清单），`--rollback` 可整目录回滚并重新 HUP/reload；
- 更新互斥：`mkdir` 锁（PID 文件 + 过期检测），防并发更新；
- 前置校验：栈必须已用热更新覆盖文件启动（检查容器挂载点），否则拒绝执行；
- 全程输出到 stdout 并落 `deploy-backups/<ts>/hot_update.log`。

## 4. 接口与数据模型

- 无 API/OIDC/数据库 schema 变更。
- 编排：新增 `docker-compose.hot.yaml`、卷 `backend-code`、`frontend-web`。
- 新增 `scripts/hot_update.sh`；`.gitignore` 增加 `deploy-backups/`。

## 5. 安全影响

- 热更新模式下后端/前端文件系统可被宿主侧 `docker cp` 改写：这是能力的核心，也是可写面。
  缓解：仅热更新形态启用、脚本强制校验与快照、SHA256 清单、日志留痕、可回滚；
  Docker API 权限本身就等于宿主机写权限，因此不新增权限边界外的风险，但要求运维限制
  能操作 Docker 的人员。
- 不放松任何生产校验（https/redis/smtp/密钥路径）；`--reload` 不进入生产。
- 迁移兼容性由既有「破坏性变更必须可迁移」规则兜底；脚本在迁移失败时中止、不换代码。

## 6. 验收标准

- [x] `docker compose -f docker-compose.yaml -f docker-compose.hot.yaml config -q` 通过；
  backend 挂载 `backend-code:/app/app` 且 `UVICORN_WORKERS` 默认 2，frontend 挂载
  `frontend-web:/usr/share/nginx/html`，基础卷（keys/uploads/data）不丢失。
- [x] `bash -n scripts/hot_update.sh` 通过；`--dry-run` 不产生任何写操作。
- [x] 隔离 compose 项目（独立网关端口）端到端：frontend 换装后新文件经网关可访问且旧入口
  no-cache；backend HUP 期间并发 `GET /readyz` 无失败，日志出现 SIGHUP 重启记录；
  gateway envsubst+reload 后 healthz 正常；`--rollback` 可恢复上一版本。
- [x] 生产校验不回归：`ENVIRONMENT=production` 相关测试全绿；后端全量 pytest 全绿。
- [x] 文档：README/部署文档/CHANGELOG 同步。

## 7. 风险

- **误用**：把 `docker-compose.dev.yaml`（Vite dev + `--reload`）当作生产热更新使用。
  文档明确两者边界；脚本只接受 `docker-compose.hot.yaml`。
- **迁移窗口**：旧代码 + 新 schema 并存窗口内，迁移必须向前兼容；破坏性变更先加新列/新表，
  代码双写，再删旧结构。
- **回滚不等于全量回滚**：数据库迁移在 `--rollback` 时不会自动 downgrade，需人工
  `alembic downgrade -1`（脚本提示）；避免在热更新期间执行不可逆迁移。
- **worker 数**：单 worker 时 SIGHUP 有短暂中断；脚本拒绝 `UVICORN_WORKERS<2`。
