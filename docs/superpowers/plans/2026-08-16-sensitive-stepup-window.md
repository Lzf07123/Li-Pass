# 敏感操作 step-up 认证窗口实施计划

> 日期：2026-08-16 ｜ 对应设计：[2026-08-16-sensitive-stepup-window-design.md](../specs/2026-08-16-sensitive-stepup-window-design.md)

## Goal

在会话维度实现 30 分钟 step-up 认证窗口：一次密码复核后，该会话内的敏感操作免再次输入密码；窗口过期/会话吊销后恢复强制复核。同步把散落的密码校验收敛为统一服务，补齐独立限流与审计。

## Architecture / Tech Stack

后端 FastAPI + SQLAlchemy 2.0 + Alembic；前端 React + TypeScript。窗口状态存 `sessions.stepup_at`，判定集中到 `app/services/stepup.py`。

## Global Constraints

- 分支 `codex/sensitive-stepup-window`；每 Task 独立提交，提交消息 `<type>: <中文简述>`。
- 安全不降级：登录不授窗、按会话隔离、固定 30 分钟窗口、复核失败限流并审计。
- 每个 Task 先写失败测试（红）→ 最小实现（绿）→ 全量回归 → 提交。
- 后端验证命令在 `backend/` 下用 `.venv` 执行；前端在 `frontend/` 下执行。

## Task 1 — 会话模型新增 stepup_at 与配置项

Create/Modify/Test：

- Modify `backend/app/models/session.py`：`stepup_at: Mapped[datetime | None]`（`DateTime(timezone=True)`）
- Modify `backend/app/core/config.py`：`stepup_window_minutes=30`、`stepup_rate_limit=5`、`stepup_rate_window_seconds=900`、`stepup_email_rate_limit=10`、`stepup_email_rate_window_seconds=900` + 校验器
- Create `backend/alembic/versions/f1a2b3c4d5e6_add_stepup_at_to_sessions.py`（revision 链自 `7f2a9d3c8e1b`）
- Modify `backend/.env.example`：注释文档化新变量
- Test `backend/tests/test_stepup_window_model.py`：`Session.__table__` 含 `stepup_at`；`Settings` 默认值与非法值校验

Consumes：无（纯模型/配置）
Produces：`Session.stepup_at`、5 个 Settings 字段

Checklist：

- [ ] 写测试断言模型列与配置默认值/边界，运行确认红
- [ ] 实现模型列 + Settings 字段与校验，迁移 upgrade/downgrade
- [ ] `python -m pytest tests/test_stepup_window_model.py -q` 绿；全量回归绿
- [ ] 提交 `feat: 会话模型新增 stepup_at 与 step-up 窗口配置`

## Task 2 — step-up 服务与显式复核端点

Create/Modify/Test：

- Create `backend/app/services/stepup.py`：`stepup_status(session)`、`authorize_stepup(request, db, user, session, password)`（限流 scopes `stepup:{email}:{ip}` 与 `stepup_email:{email}`、审计 `stepup_verify_success`/`stepup_failed`/`stepup_required`、429/400/403 语义、naive→UTC 归一化）
- Modify `backend/app/schemas/auth.py`：新增 `StepUpVerifyRequest{password}`
- Modify `backend/app/api/routes/users.py`：`GET /api/v1/me/step-up`（状态）、`POST /api/v1/me/step-up`（复核）
- Create `backend/tests/test_stepup.py`：未登录 401；开窗前后状态；错密码 400；限流 429；审计动作落库；第二会话隔离；登录不授窗；窗口过期（直接前移 `stepup_at`）后 403

Consumes：Task 1 的模型列与配置
Produces：`authorize_stepup` 服务、`/me/step-up` 两端点

Checklist：

- [ ] 写 `test_stepup.py`，运行确认红
- [ ] 实现服务、schema 与端点
- [ ] `python -m pytest tests/test_stepup.py -q` 绿；全量回归绿
- [ ] 提交 `feat: 新增 step-up 复核服务与状态/验证端点`

## Task 3 — 用户中心与 2FA 敏感端点接入

Create/Modify/Test：

- Modify `backend/app/schemas/auth.py`：`PasswordChange`/`PasswordConfirm`/`TwoFaTotpEnable` 的 `current_password` 改可选
- Modify `backend/app/api/routes/users.py`：`change_password`、`delete_own_account` 改为 `authorize_stepup`；改密成功后当前会话窗口保留（已由授权写入）
- Modify `backend/app/api/routes/twofa.py`：删除 `_require_password`，4 个端点加 `Request`/`get_current_session` 依赖并调用服务
- Modify `backend/tests/test_twofa_settings.py`、`test_user_center.py`、`test_account_deletion.py`：缺密码断言 422→403「需要重新验证密码」；补窗口内免密用例
- Create `backend/tests/test_stepup_endpoints.py`：改密开窗→2FA 开关免密→注销免密（跨端点共享窗口）

Consumes：Task 2 服务
Produces：用户中心/2FA 端点窗口语义

Checklist：

- [ ] 更新/新增测试，运行确认红
- [ ] 改造两个路由文件与 schema
- [ ] 单测绿；全量回归绿
- [ ] 提交 `feat: 用户中心与 2FA 敏感操作接入 step-up 窗口`

## Task 4 — 管理端敏感端点接入

Create/Modify/Test：

- Modify `backend/app/api/routes/admin_users.py`：`AdminResetPassword`/`AdminDeleteUser`/`AdminBatchDeleteUser` 的 `current_password` 改可选；`batch_update_users`、`update_user`（角色变更时）、`reset_password`、`reset_twofa`、`batch_delete_users`、`delete_user` 接入服务（新增 `Request`/`get_current_session` 依赖）
- Modify `backend/app/api/routes/admin_clients.py`：`delete_client`、`reset_secret` 接入服务
- Modify `backend/tests/test_admin_stepup_auth.py`、`test_admin_users_management.py`、`test_admin_batch_ops.py`、`test_admin_clients.py`、`test_rate_limit_and_audit.py`：缺密码断言 422/400→403；补「先 `POST /me/step-up` 开窗再免密执行」用例

Consumes：Task 2 服务
Produces：管理端端点窗口语义

Checklist：

- [ ] 更新/新增测试，运行确认红
- [ ] 改造两个路由文件
- [ ] 单测绿；全量回归绿
- [ ] 提交 `feat: 管理端敏感操作接入 step-up 窗口`

## Task 5 — 前端 hook 与三个页面接入

Create/Modify/Test：

- Modify `frontend/src/api/client.ts`：新增 `meApi.stepUpStatus()`、`meApi.stepUpVerify(password)`；`changePassword`/`deleteAccount`/2FA/admin 相关方法的 `current_password` 改为可选
- Create `frontend/src/hooks/useStepUp.ts`：状态缓存（30 秒）+ `refresh()` + `verify(password)`，403「需要重新验证密码」时重置缓存
- Create `frontend/src/components/StepUpNotice.tsx`：窗口内提示条（沿用 notice 视觉）
- Modify `frontend/src/pages/DashboardPage.tsx`：改密/2FA 开关/注销弹窗按窗口状态决定密码是否必填
- Modify `frontend/src/pages/AdminUsersPanel.tsx`：重置密码/重置 2FA/删除/批量删除同理
- Modify `frontend/src/pages/AdminClientsPage.tsx`：删除应用/重置密钥同理
- Create `frontend/src/__tests__/useStepUp.test.tsx`；更新 `DashboardTwofa.test.tsx`/`AdminUsersPanel.test.tsx`/`AdminClientsPage.test.tsx`

Consumes：Task 2–4 的 API 契约
Produces：窗口内免密 UX

Checklist：

- [ ] 写 hook 测试确认红
- [ ] 实现 client/hook/组件并接入三个页面
- [ ] `npx tsc -b && npm run lint && npm test` 绿
- [ ] 提交 `feat: 前端敏感操作接入 30 分钟免复核窗口`

> 执行说明：Task 3 与 Task 4 共用 `PasswordConfirm` schema（必填改可选会同时影响用户中心与管理端），
> 为保持每个提交点测试全绿，两者合并为一次提交 `feat: 用户中心/2FA/管理端敏感操作接入 step-up 窗口`；
> 测试文件仍按域拆分（`test_stepup_endpoints.py` / `test_admin_stepup_window.py`）。

## Task 6 — 文档、CHANGELOG 与全量验证

Create/Modify/Test：

- Modify `CHANGELOG.md`：功能（30 分钟 step-up 窗口）+ 安全加固（统一限流与审计）
- Modify `docs/deployment.md`：环境变量表新增 5 项、限流小节补 step-up 说明
- Modify `README.md`：用户中心特性补充「敏感操作二次认证（30 分钟免复核窗口）」
- Modify `frontend/src/api/types.ts`（如需 `StepUpStatus` 类型）

验证：

- [ ] `cd backend && .venv/bin/python -m pytest -q` 全绿
- [ ] 真实 PostgreSQL：`alembic upgrade head && alembic downgrade -1 && alembic upgrade head` 往返
- [ ] `cd frontend && npx tsc -b && npm run lint && npm test && npm run build` 全绿
- [ ] 依赖安全：后端 `pip-audit`、前端 `npm audit --omit=dev`（依赖未变，确认无新增）
- [ ] 提交 `docs: 同步敏感操作 step-up 窗口文档与变更记录`

## 收尾

- 合并 `codex/sensitive-stepup-window` 回 `main`（保留 merge 记录）
