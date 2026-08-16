# 生产级热更新实施计划

> 日期：2026-08-17 ｜ 对应设计：[2026-08-17-production-hot-update-design.md](../specs/2026-08-17-production-hot-update-design.md)

## Goal

交付单节点 compose 的生产级零停机热更新：前端卷换装、后端 uvicorn 优雅回收、网关 reload，
配套 `scripts/hot_update.sh`（校验/快照/回滚/锁/审计）与文档。

## Global Constraints

- 分支 `codex/production-hot-update`；每 Task 独立提交且提交点验证全绿；
- 安全不降级：默认生产编排保持不可变；`--reload`/Vite dev 不进入生产；
- 脚本 POSIX-ish bash（macOS/Linux 均可跑），不依赖 GNU 专有工具；`bash -n` 通过；
- 任何写操作前必须有宿主侧快照与 SHA256 清单。

## Task 1 — 编排覆盖文件与忽略项

- Create `docker-compose.hot.yaml`：backend 增加 `backend-code:/app/app`（保留
  keys/uploads/data 卷）、`UVICORN_WORKERS` 默认 2；frontend 增加
  `frontend-web:/usr/share/nginx/html`；新增同名命名卷。
- Modify `.gitignore`：`deploy-backups/`。

Consumes：现有 `docker-compose.yaml` 拓扑
Produces：热更新形态的编排入口

Checklist：

- [ ] `docker compose -f docker-compose.yaml -f docker-compose.hot.yaml config -q` 通过
- [ ] 确认合并后 backend/frontend 卷与 workers 符合设计
- [ ] 提交 `chore: 生产热更新编排覆盖文件与备份目录忽略`

## Task 2 — hot_update.sh 骨架（锁/快照/校验/健康等待）

- Create `scripts/hot_update.sh`：公共函数（日志、compose 命令封装、`--dry-run` 分流、
  mkdir 互斥锁、宿主侧快照 + SHA256、backend/frontend 健康等待、前置校验）

Consumes：docker compose CLI
Produces：可复用的更新原语

Checklist：

- [ ] `bash -n` 通过；`--dry-run` 输出命令但零写操作
- [ ] 快照目录生成 SHA256 清单；锁防并发
- [ ] 提交 `feat: 热更新脚本骨架（锁/快照/校验）`

## Task 3 — frontend 换装与 gateway reload

- Modify `scripts/hot_update.sh`：`frontend` 子命令（快照 → 复制 dist → nginx reload）、
  `gateway` 子命令（envsubst + reload）、`--rollback` 对这两者的恢复

Checklist：

- [ ] 隔离栈端到端：换装后新文件经网关可访问；rollback 恢复旧文件
- [ ] 提交 `feat: 前端静态产物热换装与网关配置热更新`

## Task 4 — backend 优雅回收

- Modify `scripts/hot_update.sh`：`backend` 子命令（前置校验 → 快照 → 可选迁移 → 复制代码 →
  SIGHUP → 健康与日志核对）、`--skip-migrations`、rollback 支持

Checklist：

- [ ] 隔离栈端到端：`UVICORN_WORKERS=2` 下 HUP 期间并发 /readyz 无失败、日志出现 SIGHUP
- [ ] 前置校验拒绝：未挂载 backend-code、workers<2
- [ ] 提交 `feat: 后端代码零停机热更新（uvicorn 优雅回收）`

## Task 5 — 文档与全量验证

- Modify `README.md`、`docs/deployment.md`、`CHANGELOG.md`：两种生产形态、脚本用法、
  适用/不适用边界、回滚与迁移注意

Checklist：

- [ ] 后端全量 pytest、前端 tsc/lint/test/build 全绿
- [ ] 隔离 compose 端到端复跑（frontend/backend/gateway/rollback）
- [ ] 提交 `docs: 生产热更新使用说明与变更日志`
