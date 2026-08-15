# 实施计划：登出语义优化（登出 SSO / 登出本网站）

日期：2026-08-16
设计：`../specs/2026-08-16-logout-semantics-design.md`

## Goal

在门户确认页、演示站与对接指南中把「登出 SSO」与「仅登出本网站」两种语义写清楚，替换现有「确认退出 / 取消」的含糊表述；后端将 `cancel` 端点重命名为语义一致的 `local-only`。

## Architecture / Tech Stack / Global Constraints

- 后端 FastAPI + SQLAlchemy；前端 React + TypeScript；演示站 Flask。
- 不改变会话吊销、回程分发、回跳白名单等安全逻辑；无数据库迁移。
- 每 Task TDD：先改测试变红 → 最小实现 → 变绿 → 独立提交。
- 提交消息 `type: 中文简述`；分支 `codex/logout-semantics`。

## Task 1：后端端点重命名 cancel → local-only

**Create/Modify/Test**

- Modify `backend/app/api/routes/oidc.py`：`cancel_logout_request` 路由路径 `/cancel` → `/local-only`，函数名与 docstring 同步改为 `local_only_logout_request`（行为不变）。
- Modify `backend/tests/test_end_session.py`：`test_cancel_returns_redirect_without_logout` 改打 `/local-only`，重命名为 `test_local_only_keeps_portal_session_and_returns_redirect`。

**Consumes**：`POST /api/v1/oauth/logout-requests/{request_id}/local-only`
**Produces**：`{"redirect_url": ...}`；门户会话保持有效。

- [x] 改测试指向 `/local-only`，跑 `pytest tests/test_end_session.py -k local_only` 变红（旧实现 404）
- [x] 改路由与函数名，测试变绿
- [x] 提交 `refactor: 登出确认请求 cancel 端点重命名为 local-only`

## Task 2：前端确认页两个语义选项

**Create/Modify/Test**

- Modify `frontend/src/api/client.ts`：`oauthApi.cancelLogoutRequest` → `localOnlyLogoutRequest`，指向 `/local-only`。
- Modify `frontend/src/pages/LogoutConfirmPage.tsx`：「确认退出」→「登出 SSO」，「取消」→「仅登出本网站」，更新副标题与后果说明（引用 `clientName`），删除「取消」。
- Modify `frontend/src/__tests__/LogoutConfirmPage.test.tsx`：按新按钮名断言，校验本地路径调用 `/local-only` 而非 `/confirm`。

**Consumes**：`GET /api/v1/oauth/logout-requests/{id}`、`POST .../confirm`、`POST .../local-only`
**Produces**：`window.location.href = redirect_url`

- [x] 改测试文案与新按钮名，跑 `vitest run LogoutConfirmPage` 变红
- [x] 改 `client.ts` 与页面实现，测试变绿
- [x] 提交 `feat: 确认页区分登出 SSO 与仅登出本网站`

## Task 3：演示站两种登出入口

**Create/Modify/Test**

- Modify `examples/demo-site/app.py`：INDEX_HTML 登录后两个按钮；新增 `POST /local-logout`（仅清本地会话回首页）；`POST /logout` 保持 SSO 路径并同步按钮文案。

**Consumes**：`POST /local-logout`、`POST /logout`
**Produces**：302 到演示站首页或 IdP `end-session`

- [x] 本地启动演示站（或静态检查路由注册），确认两路由存在
- [x] 提交 `feat: 演示站区分登出本网站与登出 SSO`

## Task 4：文档与变更记录

**Create/Modify/Test**

- Modify `docs/oidc-integration.md`：§7 增补「两种登出语义」小节并更新 §7.1 的确认页描述。
- Modify `CHANGELOG.md`：「行为变更」区记录端点重命名、确认页与演示站文案变化。

- [x] 提交 `docs: 同步登出语义文档与变更记录`

## 全量验证（收尾前）

```bash
cd backend && .venv/bin/python -m pytest -q
cd frontend && npx tsc -b && npm run lint && npm test && npm run build
```
