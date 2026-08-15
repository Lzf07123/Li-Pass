# 实施计划：活跃对接网站会话感知

日期：2026-08-16
设计：`../specs/2026-08-16-active-site-session-awareness-design.md`

## Goal

维护 `oidc_client_sessions` 生命周期（撤销会话同步吊销链接、重新授权激活），并在应用广场展示每网站的活跃登录设备数。

## Task 1：链接生命周期服务

- Modify `backend/app/services/federated_logout.py`：`revoke_session_links`、`revoke_user_links`。
- Create `backend/tests/test_client_session_links.py`：批量/按用户吊销、幂等。
- 提交 `feat: 客户端会话链接吊销服务`

## Task 2：撤销路径联动

- Modify `backend/app/api/routes/users.py`：单会话撤销与退出所有设备后吊销链接。
- Modify `backend/app/api/routes/auth.py`：门户登出吊销该用户全部链接。
- Modify `backend/app/api/routes/admin_sessions.py`：单/批量/全部下线后吊销链接。
- Modify `backend/app/api/routes/oidc.py`：换令牌时激活已吊销链接。
- 相关测试更新与新增。
- 提交 `feat: 会话撤销联动吊销/激活客户端链接`

## Task 3：活跃计数与前端展示

- Modify `backend/app/schemas/auth.py`：`AppOut.active_sessions`。
- Modify `backend/app/api/routes/users.py`：`list_apps` 计算活跃链接数。
- Modify `frontend/src/api/types.ts`、`DashboardPage.tsx`：徽标展示。
- 测试。
- 提交 `feat: 应用广场展示活跃登录设备数`

## Task 4：文档

- CHANGELOG 功能/行为变更。
- 提交 `docs: 同步会话感知变更记录`
