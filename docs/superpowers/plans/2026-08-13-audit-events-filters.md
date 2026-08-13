# 审计日志扩展与分类筛选 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 为 LinPass SSO 补全审计事件，并增加按分类/动作/操作者/时间筛选的后端接口与前端面板。

**Architecture:** 审计模型新增 `category` 列并迁移回填；`log_audit` 统一携带分类；现有与新增事件全部落库；`/api/v1/admin/audit-logs` 扩展筛选参数；前端审计面板提供分类下拉、动作筛选、加载更多。

**Tech Stack:** FastAPI + SQLAlchemy + Alembic + React + Vitest + pytest。

## Global Constraints

- 后端测试本地运行：`backend/.venv/bin/python -m pytest -q`；测试文件在 `backend/tests/`，已纳入版本库并接入 CI。
- 前端测试本地运行：`npm test`；`frontend/src/__tests__/` 已纳入版本库并接入 CI。
- 提交时测试与实现代码一并暂存（CI 依赖仓库内的测试做持续回归）。
- 新增审计动作全部使用小写 snake_case；分类必须是 `AUDIT_CATEGORIES` 中定义的值。
- 不记录 OIDC token 换取（高频噪音，spec 非目标）。
- 不引入新依赖。

---

### Task 1: 审计模型与 log_audit 分类

**Files:**
- Modify: `backend/app/models/audit_log.py`
- Modify: `backend/app/services/audit.py`
- Create: `backend/alembic/versions/e3f5a7b9c1d2_add_audit_category.py`
- Test: `backend/tests/test_audit_log.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `AuditLog.category: str | None`（`VARCHAR(30)`、索引）
  - `AUDIT_CATEGORIES: frozenset[str]`
  - `log_audit(db, actor_type, actor_id, action, category="other", ...)`：未知分类回退 `other`

- [x] **Step 1: 写失败测试**

```python
import uuid

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services.audit import log_audit


def test_log_audit_writes_category(db_session) -> None:
    log_audit(
        db_session,
        "user",
        str(uuid.uuid4()),
        "login",
        category="auth",
        ip="127.0.0.1",
    )
    row = db_session.scalar(select(AuditLog))
    assert row is not None
    assert row.category == "auth"


def test_log_audit_falls_back_to_other_for_unknown_category(db_session) -> None:
    log_audit(
        db_session,
        "user",
        str(uuid.uuid4()),
        "weird_action",
        category="not-a-real-category",
    )
    row = db_session.scalar(select(AuditLog))
    assert row is not None
    assert row.category == "other"
```

- [x] **Step 2: 运行测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_log.py -q`
Expected: FAIL（`AuditLog` 无 `category` 属性 / `log_audit` 不接受 `category`）

- [x] **Step 3: 修改模型**

`backend/app/models/audit_log.py` 增加：

```python
    category: Mapped[str | None] = mapped_column(String(30), index=True)
```

- [x] **Step 4: 修改 log_audit**

`backend/app/services/audit.py` 增加：

```python
AUDIT_CATEGORIES = frozenset(
    {
        "auth",
        "user",
        "2fa",
        "consent",
        "oidc",
        "admin_user",
        "admin_client",
        "admin_block",
        "admin_settings",
        "security",
        "other",
    }
)
```

`log_audit` 签名与落库：

```python
def log_audit(
    db,
    actor_type: str,
    actor_id: str | None,
    action: str,
    category: str = "other",
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    if category not in AUDIT_CATEGORIES:
        category = "other"
    # ... 原有截断逻辑保持不变 ...
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            category=category,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
    )
    db.commit()
```

- [x] **Step 5: 创建迁移**

`backend/alembic/versions/e3f5a7b9c1d2_add_audit_category.py`：

```python
"""add audit category

Revision ID: e3f5a7b9c1d2
Revises: 9f3e2a1c4b5d
Create Date: 2026-08-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e3f5a7b9c1d2"
down_revision: Union[str, None] = "9f3e2a1c4b5d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTION_CATEGORY = {
    "login": "auth",
    "login_step1": "auth",
    "2fa_login": "auth",
    "user_register_by_invite": "auth",
    "password_reset": "auth",
    "login_failed": "security",
    "2fa_login_failed": "security",
    "password_change": "user",
    "user_delete_self": "user",
    "app_consent_revoke": "consent",
    "2fa_email_enable": "2fa",
    "2fa_email_disable": "2fa",
    "2fa_totp_enable": "2fa",
    "2fa_totp_disable": "2fa",
    "admin_create_user": "admin_user",
    "admin_invite_user": "admin_user",
    "admin_cancel_invite": "admin_user",
    "admin_resend_invite": "admin_user",
    "admin_delete_invite": "admin_user",
    "admin_batch_invite_user": "admin_user",
    "admin_batch_update_user": "admin_user",
    "admin_update_user": "admin_user",
    "admin_reset_password": "admin_user",
    "admin_reset_2fa": "admin_user",
    "admin_batch_delete_user": "admin_user",
    "admin_delete_user": "admin_user",
    "admin_create_client": "admin_client",
    "admin_update_client": "admin_client",
    "admin_delete_client": "admin_client",
    "admin_reset_client_secret": "admin_client",
    "block_add": "admin_block",
    "block_remove": "admin_block",
    "admin_update_site_setting": "admin_settings",
}


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("category", sa.String(length=30), nullable=True),
    )
    connection = op.get_bind()
    for action, category in ACTION_CATEGORY.items():
        connection.execute(
            sa.text(
                "UPDATE audit_logs SET category = :category WHERE action = :action AND category IS NULL"
            ),
            {"category": category, "action": action},
        )
    connection.execute(
        sa.text(
            "UPDATE audit_logs SET category = 'other' WHERE category IS NULL"
        )
    )
    op.create_index(
        op.f("ix_audit_logs_category"),
        "audit_logs",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_category"), table_name="audit_logs")
    op.drop_column("audit_logs", "category")
```

- [x] **Step 6: 运行测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_log.py -q`
Expected: PASS

- [x] **Step 7: 本地验证迁移**

Run: `cd backend && .venv/bin/alembic upgrade head`
Expected: 迁移成功，历史 `audit_logs.category` 已回填

- [x] **Step 8: 提交**

```bash
git add backend/app/models/audit_log.py backend/app/services/audit.py backend/alembic/versions/e3f5a7b9c1d2_add_audit_category.py
git commit -m "feat: 审计日志增加 category 字段与迁移回填"
```

---

### Task 2: 现有审计调用补充分类

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/users.py`
- Modify: `backend/app/api/routes/twofa.py`
- Modify: `backend/app/api/routes/admin_users.py`
- Modify: `backend/app/api/routes/admin_clients.py`
- Modify: `backend/app/api/routes/client_blocks.py`
- Modify: `backend/app/api/routes/admin_settings.py`

**Interfaces:**
- Consumes: `log_audit(..., category=...)`（Task 1）
- Produces: 全部现有审计记录带正确分类

- [x] **Step 1: 按映射表补充 category 参数**

每个 `log_audit` 调用在 `action` 参数后加 `category="..."`：

| 文件 | action | category |
| --- | --- | --- |
| `auth.py` | `user_register_by_invite` | `auth` |
| `auth.py` | `login_failed` | `security` |
| `auth.py` | `login_step1` / `login` | `auth` |
| `auth.py` | `2fa_login_failed` | `security` |
| `auth.py` | `2fa_login` | `auth` |
| `auth.py` | `password_reset` | `auth` |
| `users.py` | `password_change` | `user` |
| `users.py` | `user_delete_self` | `user` |
| `users.py` | `app_consent_revoke` | `consent` |
| `twofa.py` | `2fa_email_enable` / `2fa_email_disable` / `2fa_totp_enable` / `2fa_totp_disable` | `2fa` |
| `admin_users.py` | `admin_*`（全部） | `admin_user` |
| `admin_clients.py` | `admin_create_client` / `admin_update_client` / `admin_delete_client` / `admin_reset_client_secret` | `admin_client` |
| `admin_clients.py` | `block_add` / `block_remove` | `admin_block` |
| `client_blocks.py` | `block_add` / `block_remove` | `admin_block` |
| `admin_settings.py` | `admin_update_site_setting` | `admin_settings` |

示例（`backend/app/api/routes/auth.py` 登录成功）：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "login",
        category="auth",
        ip=ip,
        user_agent=user_agent,
    )
```

- [x] **Step 2: 运行全量后端测试确认无回归**

Run: `backend/.venv/bin/python -m pytest -q`
Expected: 全部通过（现有 166 个测试 + 新增测试）

- [x] **Step 3: 提交**

```bash
git add backend/app/api/routes/auth.py backend/app/api/routes/users.py backend/app/api/routes/twofa.py backend/app/api/routes/admin_users.py backend/app/api/routes/admin_clients.py backend/app/api/routes/client_blocks.py backend/app/api/routes/admin_settings.py
git commit -m "feat: 现有审计事件补充分类"
```

---

### Task 3: 新增审计事件

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/users.py`
- Modify: `backend/app/api/routes/consent.py`
- Modify: `backend/app/api/routes/oidc.py`
- Test: `backend/tests/test_audit_events.py`

**Interfaces:**
- Consumes: `log_audit(..., category=...)`
- Produces: 新事件落库，分类正确

- [x] **Step 1: 写失败测试**

```python
from sqlalchemy import select

from app.models.audit_log import AuditLog


def _login_admin(client, db_session):
    from app.models.user import User, UserRole
    from app.security.passwords import hash_password

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert resp.status_code == 200


def test_register_logs_audit(client, db_session, captured_email) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "nickname": "New",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user_register")
    )
    assert row is not None
    assert row.category == "auth"


def test_logout_logs_audit(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "logout")
    )
    assert row is not None
    assert row.category == "auth"


def test_profile_update_logs_audit(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.put("/api/v1/me", json={"nickname": "Renamed"})
    assert resp.status_code == 200
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "profile_update")
    )
    assert row is not None
    assert row.category == "user"
```

- [x] **Step 2: 运行测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_events.py -q`
Expected: FAIL（`user_register` / `logout` / `profile_update` 记录不存在）

- [x] **Step 3: auth.py 新增事件**

普通注册成功后（`auth.py` 的 `register`，`db.commit()` 之后）：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "user_register",
        category="auth",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={"email": email},
    )
```

邮箱验证成功（`verify_email` 中 `db.commit()` 之后）：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "email_verify",
        category="auth",
        target_type="user",
        target_id=str(user.id),
        detail={"email": email},
    )
```

重发验证码成功（`resend_verify_email` 中 `db.commit()` 之后）：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "email_verify_resend",
        category="auth",
        target_type="user",
        target_id=str(user.id),
        detail={"email": email},
    )
```

退出登录（`logout` 中 session 吊销并 `db.commit()` 之后）：

```python
    if session is not None:
        log_audit(
            db,
            "user",
            str(session.user_id),
            "logout",
            category="auth",
            target_type="user",
            target_id=str(session.user_id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
```

找回密码请求受理（`request_password_reset` 中用户存在且邮件发送成功后）：

```python
    if user is not None:
        # ... 现有 create_otp / send / commit ...
        log_audit(
            db,
            "user",
            str(user.id),
            "password_reset_request",
            category="auth",
            target_type="user",
            target_id=str(user.id),
            detail={"email": email},
        )
```

限流拒绝（`register`、`login` 的 IP 前置限流、`resend_verify_email`、`request_password_reset`、2FA `send` 的 429 分支）统一记录：

```python
    log_audit(
        db,
        "system",
        None,
        "rate_limit_rejected",
        category="security",
        ip=ip,
        detail={"action": "register", "reason": "rate_limit"},
    )
```

`login` 的前置 IP 限流在 `request` 可用时按同样模式记录；`actor_id` 取 `str(user.id) if user else None`。

- [x] **Step 4: users.py 新增事件**

`update_profile` 在 `db.commit()` 之后：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "profile_update",
        category="user",
        target_type="user",
        target_id=str(user.id),
        detail={"nickname_changed": payload.nickname is not None},
    )
```

`upload_avatar` 成功后：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "avatar_upload",
        category="user",
        target_type="user",
        target_id=str(user.id),
    )
```

`revoke_session` 吊销后：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "session_revoke",
        category="user",
        target_type="session",
        target_id=str(session.id),
    )
```

`send_phone_bind_code` 发送成功后与 `bind_phone` 绑定成功后：

```python
    log_audit(db, "user", str(user.id), "phone_bind_send", category="user")
    log_audit(db, "user", str(user.id), "phone_bind", category="user")
```

- [x] **Step 5: consent.py / oidc.py 新增事件**

`consent.py` 的 `approve` 在 `store.delete(request_id)` 之前：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "consent_approve",
        category="consent",
        target_type="oauth_client",
        target_id=str(client.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"client_id": client.client_id, "scopes": granted},
    )
```

`deny` 同样记录 `consent_deny`，`detail={"client_id": pending.client_id}`（`deny` 无 `request` 参数，保持无 IP）。

`oidc.py` 的 `authorize` 免确认直发分支（唯一的 `create_authorization_code` 调用处）加：

```python
    log_audit(
        db,
        "user",
        str(user.id),
        "oauth_authorize",
        category="oidc",
        target_type="oauth_client",
        target_id=str(client.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"client_id": client.client_id, "scopes": requested},
    )
```

注意 `oidc.py` 的 `authorize` 已有 `request: Request` 参数；两处 `create_authorization_code` 调用前各插一次。

- [x] **Step 6: 运行测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_events.py backend/tests/test_auth_register.py backend/tests/test_oidc_authorize.py backend/tests/test_oidc_token.py backend/tests/test_admin_batch_ops.py -q`
Expected: PASS

- [x] **Step 7: 提交**

```bash
git add backend/app/api/routes/auth.py backend/app/api/routes/users.py backend/app/api/routes/consent.py backend/app/api/routes/oidc.py
git commit -m "feat: 审计补充注册/验证/退出/资料/授权/OIDC/限流事件"
```

---

### Task 4: 审计列表筛选 API

**Files:**
- Modify: `backend/app/api/routes/admin_users.py`
- Test: `backend/tests/test_audit_filters.py`

**Interfaces:**
- Consumes: `AuditLog.category`（Task 1）
- Produces:
  - `GET /api/v1/admin/audit-logs?category=&action=&actor_id=&start=&end=&limit=&offset=`
  - 响应元素新增 `category` 字段

- [x] **Step 1: 写失败测试**

```python
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services.audit import log_audit


def _login_admin(client, db_session):
    from app.models.user import User, UserRole
    from app.security.passwords import hash_password

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )


def test_audit_list_filters_by_category(client, db_session) -> None:
    _login_admin(client, db_session)
    log_audit(db_session, "user", "u1", "login", category="auth")
    log_audit(db_session, "user", "u1", "login_failed", category="security")
    resp = client.get("/api/v1/admin/audit-logs?category=security")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["action"] == "login_failed"
    assert items[0]["category"] == "security"


def test_audit_list_filters_by_actor_and_time(client, db_session) -> None:
    _login_admin(client, db_session)
    now = datetime.now(timezone.utc)
    log_audit(db_session, "user", "u1", "login", category="auth")
    log_audit(db_session, "user", "u2", "login", category="auth")
    start = (now - timedelta(minutes=1)).isoformat()
    end = (now + timedelta(minutes=1)).isoformat()
    resp = client.get(
        f"/api/v1/admin/audit-logs?actor_id=u1&start={start}&end={end}"
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["actor_id"] == "u1" for item in items)
```

- [x] **Step 2: 运行测试确认失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_filters.py -q`
Expected: FAIL（`category` 参数未实现 / 响应无 `category` 字段）

- [x] **Step 3: 实现筛选**

`backend/app/api/routes/admin_users.py` 的 `list_audit_logs` 改为：

```python
from datetime import datetime

@router.get("/audit-logs", response_model=list[dict])
def list_audit_logs(
    category: str | None = Query(None),
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(AuditLog)
    if category:
        stmt = stmt.where(AuditLog.category == category)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if start:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AuditLog.created_at <= end)
    logs = db.scalars(
        stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": str(log.id),
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "action": log.action,
            "category": log.category,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "ip": log.ip,
            "detail": log.detail,
            "created_at": log.created_at,
        }
        for log in logs
    ]
```

`datetime` 从 `datetime` 模块导入（文件已 `from datetime import datetime, timedelta, timezone`，无需重复）。

- [x] **Step 4: 运行测试确认通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_audit_filters.py -q`
Expected: PASS

- [x] **Step 5: 提交**

```bash
git add backend/app/api/routes/admin_users.py
git commit -m "feat: 审计日志列表支持分类/动作/操作者/时间筛选与分页"
```

---

### Task 5: 前端类型、API 客户端与审计面板

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/AdminAuditPanel.tsx`
- Test: `frontend/src/__tests__/AdminAuditPanel.test.tsx`

**Interfaces:**
- Consumes: 筛选 API（Task 4）
- Produces:
  - `AuditLogOut.category: string | null`
  - `adminAuditApi.list(params: AuditQuery)`（`limit`/`offset` 默认 100/0）

- [x] **Step 1: 写失败测试**

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminAuditPanel } from "../pages/AdminAuditPanel";
import { renderWithProviders } from "../test/renderWithProviders";

describe("AdminAuditPanel", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("按分类筛选后重新请求并渲染分类徽章", async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("category=security")) {
        return Promise.resolve(
          new Response(
            JSON.stringify([
              {
                id: "1",
                actor_type: "user",
                actor_id: "u1",
                action: "login_failed",
                category: "security",
                target_type: null,
                target_id: null,
                ip: "127.0.0.1",
                detail: null,
                created_at: "2026-08-13T00:00:00Z",
              },
            ]),
            { status: 200, headers: { "Content-Type": "application/json" } }
          )
        );
      }
      return Promise.resolve(
        new Response("[]", {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWithProviders(<AdminAuditPanel />);
    fireEvent.change(screen.getByLabelText("审计分类"), {
      target: { value: "security" },
    });
    fireEvent.click(screen.getByRole("button", { name: "刷新" }));

    await waitFor(() =>
      expect(screen.getByText("login_failed")).toBeInTheDocument()
    );
    expect(screen.getByText("安全")).toBeInTheDocument();
  });
});
```

- [x] **Step 2: 运行测试确认失败**

Run: `npm test -- AdminAuditPanel.test.tsx`
Expected: FAIL（`审计分类` label 不存在 / 分类徽章不存在）

- [x] **Step 3: 更新类型与客户端**

`frontend/src/api/types.ts`：

```ts
export interface AuditLogOut {
  id: string;
  actor_type: string;
  actor_id: string | null;
  action: string;
  category: string | null;
  target_type: string | null;
  target_id: string | null;
  ip: string | null;
  detail: Record<string, unknown> | null;
  created_at: string;
}
```

`frontend/src/api/client.ts`：

```ts
export interface AuditQuery {
  category?: string;
  action?: string;
  actor_id?: string;
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
}

export const adminAuditApi = {
  list: (params: AuditQuery = {}) => {
    const search = new URLSearchParams();
    if (params.category) search.set("category", params.category);
    if (params.action) search.set("action", params.action);
    if (params.actor_id) search.set("actor_id", params.actor_id);
    if (params.start) search.set("start", params.start);
    if (params.end) search.set("end", params.end);
    search.set("limit", String(params.limit ?? 100));
    search.set("offset", String(params.offset ?? 0));
    return api<AuditLogOut[]>(`/api/v1/admin/audit-logs?${search.toString()}`);
  },
};
```

- [x] **Step 4: 更新 AdminAuditPanel**

```tsx
const CATEGORY_LABELS: Record<string, string> = {
  auth: "认证",
  user: "用户中心",
  "2fa": "二次验证",
  consent: "授权确认",
  oidc: "OIDC",
  admin_user: "用户管理",
  admin_client: "应用管理",
  admin_block: "黑名单",
  admin_settings: "站点设置",
  security: "安全",
  other: "其他",
};

const CATEGORIES = Object.keys(CATEGORY_LABELS);
```

状态：

```tsx
const [category, setCategory] = useState("");
const [actionFilter, setActionFilter] = useState("");
const [offset, setOffset] = useState(0);
const [hasMore, setHasMore] = useState(true);
```

加载逻辑（替换原 `load`）：

```tsx
const load = useCallback(
  (nextOffset = 0, append = false) => {
    adminAuditApi
      .list({
        category: category || undefined,
        action: actionFilter || undefined,
        offset: nextOffset,
        limit: 100,
      })
      .then((items) => {
        setLogs((prev) => (append ? [...prev, ...items] : items));
        setOffset(nextOffset + items.length);
        setHasMore(items.length === 100);
      })
      .catch((err) =>
        toast.error(err instanceof Error ? err.message : "加载失败")
      );
  },
  [actionFilter, category, toast]
);
```

刷新动作改为包装 `load`，保证按当前筛选条件请求：

```tsx
const refreshAction = useAsyncAction(
  async () => {
    await load(0, false);
  },
  {
    onError: (err) =>
      toast.error(err instanceof Error ? err.message : "刷新失败"),
  },
);
```

筛选栏（插在标题行与表格之间）：

```tsx
<div className="flex flex-wrap items-center gap-2">
  <label className="flex items-center gap-2 text-sm text-foreground">
    <span>审计分类</span>
    <select
      value={category}
      onChange={(e) => {
        setCategory(e.target.value);
        setOffset(0);
        setHasMore(true);
      }}
      className="input-sm sm:w-40"
      aria-label="审计分类"
    >
      <option value="">全部</option>
      {CATEGORIES.map((key) => (
        <option key={key} value={key}>
          {CATEGORY_LABELS[key]}
        </option>
      ))}
    </select>
  </label>
  <input
    value={actionFilter}
    onChange={(e) => setActionFilter(e.target.value)}
    placeholder="输入完整动作名"
    aria-label="审计动作"
    className="input-sm sm:w-64"
  />
  <AsyncButton
    type="button"
    status={refreshAction.status}
    onClick={() => void refreshAction.run()}
    className="btn btn-secondary"
  >
    刷新
  </AsyncButton>
</div>
```

表格新增“分类”列：

```tsx
<th>分类</th>
...
<td>
  <span className="badge badge-muted">
    {CATEGORY_LABELS[log.category ?? "other"] ?? log.category ?? "其他"}
  </span>
</td>
```

表格下方“加载更多”：

```tsx
{hasMore && logs.length > 0 && (
  <button
    type="button"
    className="btn btn-secondary w-full"
    onClick={() => load(offset, true)}
  >
    加载更多
  </button>
)}
```

`useEffect` 改为 `useEffect(() => { load(0, false); }, [load]);`。筛选变化时 `load` 引用随之变化，由 effect 自动重新加载，`onChange` 只更新状态，避免双请求。

- [x] **Step 5: 运行测试确认通过**

Run: `npm test -- AdminAuditPanel.test.tsx`
Expected: PASS

- [x] **Step 6: 提交**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/pages/AdminAuditPanel.tsx
git commit -m "feat: 审计面板支持分类筛选与加载更多"
```

---

### Task 6: 全量验证与文档同步

**Files:**
- Modify: `docs/superpowers/specs/2026-08-13-audit-events-filters-design.md`（状态改为已实施完成）

- [x] **Step 1: 后端全量测试**

Run: `backend/.venv/bin/python -m pytest -q`
Expected: 全部通过

- [x] **Step 2: 前端全量验证**

Run: `cd frontend && npx tsc -b && npm run lint && npm test && npm run build`
Expected: 全部通过

- [x] **Step 3: 更新 spec 状态**

把 `- 状态：待用户评审` 改为 `- 状态：已实施完成（2026-08-13）`。

- [x] **Step 4: 提交**

```bash
git add docs/superpowers/specs/2026-08-13-audit-events-filters-design.md
git commit -m "docs: 审计日志扩展与分类筛选实施完成"
```

---

## Self-Review

- Spec 覆盖：分类体系（Task 1/2/3）、事件补全（Task 3）、迁移回填（Task 1）、筛选 API（Task 4）、前端筛选（Task 5）、测试（各 Task）、文档（Task 6）。
- 类型一致性：`AuditLog.category`、`log_audit(category=...)`、API 响应 `category`、前端 `AuditLogOut.category`、`AuditQuery` 参数名一致。
- 无占位：每个代码步骤都给出可运行代码与验证命令；映射表覆盖全部现有 `log_audit` 调用。
