# 安全、UI 与会话守护全量加固实施计划

## Goal

落地 `docs/superpowers/specs/2026-08-16-security-ui-session-hardening-design.md` 的全部修复项，
TDD、逐 Task 独立提交，全量验证后合并 main。

## Architecture

FastAPI + SQLAlchemy 2.0（backend）+ React/Vite/TS（frontend）+ nginx 网关；无新依赖（DNS 固定
复用 httpcore 公开 API，属 httpx 传递依赖）。分支 `codex/hardening-round-1`。

## Tech Stack

Python 3.12 / FastAPI / PyJWT / argon2-cffi / httpx+httpcore；Node 22 / React 19 / vitest / oxlint。

## Global Constraints

- 每个 Task：先写失败测试 → 验证红 → 最小实现 → 验证绿 → 独立提交（type: 中文简述）。
- 不降低任何既有安全防护；OIDC 契约改动同步 `docs/oidc-integration.md`。
- 动效尊重 `prefers-reduced-motion`；文案与令牌以现有前端为准。

## Task 1 登录枚举时序 + 登录/注册 Origin 校验

- Modify: `backend/app/api/routes/auth.py`（dummy hash 常量 + login 路径）、`backend/app/main.py`（Origin 校验扩展）
- Modify: `backend/app/core/config.py`（无新配置，本 Task 不涉及）
- Test: `backend/tests/test_auth_login.py`、`backend/tests/test_auth_register.py`
- Consumes: `POST /api/v1/auth/login`、`POST /api/v1/auth/register`
- [ ] 失败测试：不存在邮箱与存在邮箱响应耗时差在可接受范围；跨站 Origin 的 login/register 被 403
- [ ] 实现并验证绿
- [ ] 提交 `fix: 抹平登录枚举时序并收紧登录/注册跨站校验`

## Task 2 可信设备撤销一致性 + 恢复码熵 + 后端 CSP

- Modify: `backend/app/api/routes/auth.py`、`backend/app/api/routes/admin_users.py`、`backend/app/services/twofa.py`、`backend/app/main.py`
- Test: `backend/tests/test_auth_password_reset.py`、`backend/tests/test_admin_users_management.py`、`backend/tests/test_twofa.py`（若存在）
- Consumes: 三条重置路径；`POST /api/v1/me/2fa/totp/enable`（恢复码长度）
- [ ] 失败测试：密码重置/管理员重置密码/重置 2FA 后可信设备被吊销；恢复码 32 位 hex；CSP 含新增指令
- [ ] 实现并验证绿
- [ ] 提交 `fix: 密码/2FA 重置统一吊销可信设备并提升恢复码熵与 CSP`

## Task 3 OIDC 合规（PKCE 全强制、token 错误格式、at_hash、nonce、长度上限、拼接修复）

- Modify: `backend/app/api/routes/oidc.py`、`backend/app/security/jwt.py`、`backend/app/services/oidc.py`
- Test: `backend/tests/test_oidc_token.py`、`backend/tests/test_oidc_authorize.py`、`backend/tests/test_jwt.py`
- Consumes: `/oauth2/authorize`、`/oauth2/token`
- [ ] 失败测试：机密客户端缺 verifier 400；错误体含 `error`；id_token 含正确 at_hash；无 nonce 时无 null；超长参数 422/400；带 query 回调用 `&` 拼接
- [ ] 实现并验证绿
- [ ] 提交 `fix: OIDC 合规——PKCE 全客户端强制、RFC6749 错误格式、at_hash 与长度上限`

## Task 4 发现文档补齐 + authorize/token 限流 + 授权请求绑定用户

- Modify: `backend/app/api/routes/oidc.py`、`backend/app/services/pending_requests.py`、`backend/app/api/routes/consent.py`、`backend/app/core/config.py`
- Test: `backend/tests/test_oidc_token.py`、`backend/tests/test_consent.py`、`backend/tests/test_pending_requests.py`
- Consumes: discovery、authorize、token、consent
- [ ] 失败测试：discovery 新增字段；authorize/token 超限 429；他人 request_id 403
- [ ] 实现并验证绿
- [ ] 提交 `fix: OIDC 发现文档补齐、端点限流与授权请求绑定用户`

## Task 5 会话空闲分钟化 + /me/session + 回程登出 DNS 固定

- Modify: `backend/app/core/config.py`、`backend/app/api/deps.py`、`backend/app/api/routes/users.py`、`backend/app/api/routes/admin_sessions.py`、`backend/app/api/routes/auth.py`（/me/session 放 users.py）、`backend/app/services/federated_logout.py`
- Test: `backend/tests/test_config_production.py`、`backend/tests/test_backchannel_dispatch.py`、新增 `backend/tests/test_session_info.py`
- Consumes: `GET /api/v1/me/session`；回程登出派发
- [ ] 失败测试：SESSION_IDLE_MINUTES 生效/校验；/me/session 字段正确；DNS 固定 backend 使用安全解析 IP 拨号
- [ ] 实现并验证绿
- [ ] 提交 `fix: 会话空闲超时分钟化、会话信息端点与回程登出 DNS 固定`

## Task 6 移除记住密码 + 前端 CSP/首帧 + 401 兜底 + next 回传

- Modify: `frontend/src/lib/remember.ts`、`frontend/src/pages/LoginPage.tsx`、`frontend/index.html`、
  `frontend/public/theme-init.js`（新增）、`frontend/public/preflight.css`（新增）、`frontend/nginx.conf.template`、
  `frontend/src/api/client.ts`、`frontend/src/App.tsx`、`frontend/src/pages/DashboardPage.tsx`、`frontend/src/pages/AdminPage.tsx`
- Test: `frontend/src/__tests__/remember.test.ts`、`frontend/src/__tests__/LoginPage.test.tsx`、`frontend/src/__tests__/ApiClient.test.ts`、`frontend/src/__tests__/DashboardPage.test.tsx`
- [ ] 失败测试：登录成功不再写入密码键；401 触发 unauthorized 事件并带 next 跳转；index.html 无内联脚本
- [ ] 实现并验证绿
- [ ] 提交 `fix: 移除明文记住密码、修复生产 CSP 首帧并补全局 401 兜底`

## Task 7 同意页身份展示 + 本地登出 + 空闲提醒 + 焦点陷阱等 UI 小项

- Modify: `backend/app/api/routes/consent.py`、`backend/app/api/routes/auth.py`（logout/local）、
  `frontend/src/pages/ConsentPage.tsx`、`frontend/src/api/client.ts`（logoutLocal/meSession）、
  `frontend/src/hooks/useSessionIdle.ts`（新增）、`frontend/src/pages/DashboardPage.tsx`、
  `frontend/src/components/Modal.tsx`、`frontend/src/components/MessageBell.tsx`
- Test: `backend/tests/test_consent.py`、`backend/tests/test_portal_logout.py`、
  `frontend/src/__tests__/ConsentPage.test.tsx`、新增 hook 测试
- [ ] 失败测试：consent info 含 user；logout/local 只吊销当前会话；Modal Tab 循环；铃铛可见性刷新
- [ ] 实现并验证绿
- [ ] 提交 `fix: 同意页身份展示、本地登出、空闲提醒与可访问性小项`

## Task 8 文档与收尾

- Modify: `CHANGELOG.md`、`docs/oidc-integration.md`、`docs/deployment.md`、`.env.example`、`backend/.env.example`、`docker-compose.yaml`、`examples/demo-site/app.py`（如需）
- [ ] 破坏性变更分区：token 错误格式、PKCE 全强制、SESSION_IDLE_MINUTES、移除记住密码
- [ ] 部署环境变量表同步；OIDC 指南 §3.3/§3.5/§7 同步
- [ ] 全量验证（后端 pytest、前端 tsc/lint/test/build、compose config）
- [ ] 提交 `docs: 同步安全加固批次文档与变更日志`
