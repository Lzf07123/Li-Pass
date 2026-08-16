# 360° 审查问题修复 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 360° 审查报告中的全部可行动项（1 中危 + 1 低危缺陷 + 5 低危加固 + 6 信息级），不降级既有安全防护与测试基线。

**Architecture:** 逐任务「失败测试 → 最小实现 → 全绿 → 独立提交」。后端遵循既有分层（中间件/服务/schema），数据变更配 Alembic 迁移；前端在既有组件内最小修改。

**Tech Stack:** FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic（后端）；React + TypeScript + vitest（前端）；Flask（演示站）。

## Global Constraints

- 分支 `codex/audit-fixes-round2`；提交消息 `<type>: <中文简述>`。
- 密码策略：长度 ≥8 且小写/大写/数字/符号 4 类至少 2 类（与前端「中」档一致）。
- 生产环境校验沿用 `_validate_web_url` 模式（http 仅开发环境允许）。
- 迁移必须能在真实 PostgreSQL 上 upgrade/downgrade 往返；downgrade 数据不可恢复的用 no-op 并注释。
- 测试默认 development 环境；生产行为用 monkeypatch 构造。

---

### Task 1: 扩展登录 CSRF Origin 守卫

**Files:**
- Modify: `backend/app/main.py`（`_origin_guarded_auth_paths`，约 153-157 行）
- Test: `backend/tests/test_auth_login.py`（新增 1 测试）

**Interfaces:**
- Consumes: 现有中间件 `csrf_origin_check`
- Produces: `_origin_guarded_auth_paths` 含 `/api/v1/auth/2fa/verify`、`/api/v1/auth/2fa/send`、`/api/v1/auth/email/verify`

- [ ] **Step 1: 写失败测试**（test_auth_login.py 追加）

```python
def test_twofa_verify_cross_site_origin_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": "any", "method": "email_otp", "code": "123456"},
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "跨站请求被拒绝"
```

- [ ] **Step 2: 运行确认失败**：`backend/.venv/bin/python -m pytest backend/tests/test_auth_login.py::test_twofa_verify_cross_site_origin_rejected -v`，预期 404（未被守卫）。
- [ ] **Step 3: 最小实现**：`_origin_guarded_auth_paths` 增加三个路径。
- [ ] **Step 4: 运行确认通过**：同上命令预期 PASS。
- [ ] **Step 5: 提交**：`fix: 2FA 验证/发送与邮箱验证纳入 Origin 白名单守卫，堵住登录 CSRF`

### Task 2: 并发注册 IntegrityError 兜底

**Files:**
- Modify: `backend/app/api/routes/auth.py`（register，约 145-218 行）
- Test: `backend/tests/test_auth_register.py`（新增 1 测试）

**Interfaces:**
- Consumes: `sqlalchemy.exc.IntegrityError`
- Produces: 注册冲突统一返回 `{"message": "注册请求已受理，验证邮件已发送"}`，HTTP 201

- [ ] **Step 1: 写失败测试**

```python
def test_register_duplicate_race_returns_uniform_message(client, monkeypatch) -> None:
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    real_commit = Session.commit
    calls = {"n": 0}

    def flaky_commit(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))
        return real_commit(self)

    monkeypatch.setattr(Session, "commit", flaky_commit)
    client.raise_server_exceptions = False
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "race@example.com", "password": "Race#2026Test!", "nickname": "竞态"},
    )
    assert response.status_code == 201
    assert response.json()["message"] == "注册请求已受理，验证邮件已发送"
```

- [ ] **Step 2: 运行确认失败**：`backend/.venv/bin/python -m pytest backend/tests/test_auth_register.py::test_register_duplicate_race_returns_uniform_message -v`，预期 500/FAIL。
- [ ] **Step 3: 最小实现**：`try: db.add(user); db.commit() except IntegrityError: db.rollback(); hash_password(payload.password); return {...}`。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: 注册接口捕获并发撞邮箱的唯一约束冲突，返回统一受理文案`

### Task 3: 回程登出校验拒绝 IPv4-mapped IPv6

**Files:**
- Modify: `backend/app/services/federated_logout.py`（`_resolve_public_host`，约 36-60 行）
- Test: `backend/tests/test_backchannel_dispatch.py`（新增 1 测试）

**Interfaces:**
- Produces: `_normalize_resolved_ip(addr) -> IPv4Address|IPv6Address`、`_validate_public_addresses(addresses) -> list[str]`

- [ ] **Step 1: 写失败测试**

```python
def test_validate_public_addresses_rejects_ipv4_mapped_ipv6() -> None:
    from app.services.federated_logout import _validate_public_addresses
    import pytest

    for bad in ("::ffff:127.0.0.1", "::ffff:10.0.0.1", "::ffff:169.254.169.254"):
        with pytest.raises(ValueError):
            _validate_public_addresses({bad})
    assert _validate_public_addresses({"8.8.8.8"}) == ["8.8.8.8"]
```

- [ ] **Step 2: 运行确认失败**：期望 AttributeError/未通过（函数不存在）。
- [ ] **Step 3: 最小实现**：`ipv4_mapped` 还原后走 `_is_unsafe_ip`。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: 回程登出地址校验拒绝 IPv4-mapped IPv6 绕过公网限制`

### Task 4: 恢复码弱哈希分支移除 + HMAC 密钥域分离 + 迁移

**Files:**
- Modify: `backend/app/services/twofa.py`（`consume_recovery_code`，约 177-195 行）
- Modify: `backend/app/security/crypto.py`（`_hmac_key`，约 69-73 行）
- Create: `backend/alembic/versions/b7e8f9a0c1d2_invalidate_recovery_codes.py`
- Test: `backend/tests/test_crypto_and_models.py`（新增 2 测试）

**Interfaces:**
- Consumes: `RecoveryCode`
- Produces: `hmac_hex` 密钥改为域分离派生；迁移清空 `recovery_codes`

- [ ] **Step 1: 写失败测试**

```python
def test_consume_recovery_code_no_legacy_sha256_fallback(client, captured_email, db_session) -> None:
    # 裸 SHA-256 存储的旧恢复码不再可消费
    from tests.helpers import register_and_login
    from app.models.recovery_code import RecoveryCode
    from app.security.tokens import hash_token
    from app.models.user import User
    from sqlalchemy import select

    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(RecoveryCode(user_id=user.id, code_hash=hash_token("legacy-code-00000001")))
    db_session.commit()
    from app.services.twofa import consume_recovery_code
    assert consume_recovery_code(db_session, user, "legacy-code-00000001") is False


def test_hmac_key_domain_separated() -> None:
    from app.security.crypto import _hmac_key, _fernet
    from app.core.config import get_settings
    import hashlib, hmac

    path = get_settings().encryption_key_path
    master = bytes(_fernet(path).encrypt(b"")[:0])  # 仅确保文件存在
    # 直接读取 master 字节验证派生关系
    from pathlib import Path
    raw = Path(path).read_bytes()
    expected = hmac.new(raw, b"lipass:hmac:v2", hashlib.sha256).digest()
    assert _hmac_key(path) == expected
    assert _hmac_key(path) != raw
```

（第二测试如需更简洁：只断言 `_hmac_key(path) != 密钥文件原始字节` 且结果稳定。）

- [ ] **Step 2: 运行确认失败**。
- [ ] **Step 3: 最小实现**：移除 legacy 分支；`_hmac_key` 域分离派生；新增迁移 `op.execute("DELETE FROM recovery_codes")`（downgrade no-op）。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: 移除恢复码弱哈希兼容分支并域分离 HMAC 密钥（迁移清空存量恢复码）`

### Task 5: 服务端密码策略

**Files:**
- Modify: `backend/app/security/passwords.py`
- Modify: `backend/app/schemas/auth.py`（RegisterRequest/InviteRegisterRequest/ConfirmPasswordResetRequest/PasswordChange）
- Modify: `backend/app/api/routes/admin_users.py`（AdminCreateUser/AdminResetPassword）
- Test: `backend/tests/test_validation_errors.py`（新增 1 测试）

**Interfaces:**
- Produces: `validate_password_strength(value: str) -> str`（不满足抛 `ValueError("密码强度不足：至少包含字母、数字或符号中的两类")`）

- [ ] **Step 1: 写失败测试**

```python
def test_weak_password_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "aaaaaaaa", "nickname": "A"},
    )
    assert response.status_code == 422
    assert "密码强度不足" in response.json()["detail"]
```

- [ ] **Step 2: 运行确认失败**（当前 201）。
- [ ] **Step 3: 最小实现**：`validate_password_strength` + 各 schema `field_validator`。
- [ ] **Step 4: 全量运行确认通过**（现有 `password123`/`newpassword456` 均为 2 类字符不受影响）。
- [ ] **Step 5: 提交**：`feat: 服务端密码复杂度校验（长度≥8 且至少两类字符）`

### Task 6: 生产环境外链头像仅 https

**Files:**
- Modify: `backend/app/schemas/auth.py`（`_validate_avatar_url`）
- Test: `backend/tests/test_user_center.py`（新增 1 测试）

- [ ] **Step 1: 写失败测试**

```python
def test_external_avatar_http_rejected_in_production(monkeypatch) -> None:
    import pytest
    from pydantic import ValidationError
    from app.schemas.auth import ProfileUpdate

    class FakeSettings:
        environment = "production"

    monkeypatch.setattr("app.schemas.auth.get_settings", lambda: FakeSettings())
    with pytest.raises(ValidationError):
        ProfileUpdate(avatar_url="http://a.png")
```

- [ ] **Step 2: 运行确认失败**（当前通过校验）。
- [ ] **Step 3: 最小实现**：https 直接放行；http 仅在非 production 放行。
- [ ] **Step 4: 运行确认通过**（开发环境既有 `http://a.png` 测试不受影响）。
- [ ] **Step 5: 提交**：`fix: 生产环境拒绝 http 外链头像，仅允许 https`

### Task 7: userinfo 401 补 WWW-Authenticate

**Files:**
- Modify: `backend/app/api/routes/oidc.py`（userinfo，约 528-545 行）
- Test: `backend/tests/test_oidc_token.py`（新增 1 测试）

- [ ] **Step 1: 写失败测试**

```python
def test_userinfo_unauthorized_includes_www_authenticate(client) -> None:
    response = client.get("/oauth2/userinfo")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == 'Bearer realm="userinfo"'
```

- [ ] **Step 2: 运行确认失败**（header 缺失）。
- [ ] **Step 3: 最小实现**：三处 401 `HTTPException` 加 `headers={"WWW-Authenticate": 'Bearer realm="userinfo"'}`。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: userinfo 401 响应补充 WWW-Authenticate（RFC 6750）`

### Task 8: 会话/应用列表空闲口径

**Files:**
- Modify: `backend/app/api/routes/users.py`（list_sessions、list_apps）
- Test: `backend/tests/test_user_center.py`（新增 1 测试）

- [ ] **Step 1: 写失败测试**

```python
def test_idle_sessions_hidden_from_list_and_app_count(client, captured_email, db_session) -> None:
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select, update
    from app.models.session import Session as SessionModel
    from app.models.user import User

    register_and_login(client, captured_email)
    now = datetime.now(timezone.utc)
    user_id = db_session.scalar(select(User.id).where(User.email == "a@example.com"))
    db_session.execute(
        update(SessionModel)
        .where(SessionModel.user_id == user_id, SessionModel.revoked_at.is_(None))
        .values(last_used_at=now - timedelta(days=30))
    )
    db_session.commit()
    assert client.get("/api/v1/sessions").status_code == 401
```

（上述用例把「当前会话」也改老会导致 401，应只改非当前会话；实现时按非当前会话构造，断言列表长度=1。）

- [ ] **Step 2: 运行确认失败**。
- [ ] **Step 3: 最小实现**：list_sessions 过滤 `expires_at >= now` 且 `last_used_at >= idle_cutoff`；list_apps 计数加 `SessionModel.last_used_at > idle_cutoff`。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: 用户会话列表与应用活跃数按空闲超时口径过滤`

### Task 9: 演示站登出漏斗

**Files:**
- Modify: `examples/demo-site/app.py`（`/logout`）

- [ ] **Step 1: 实现**：`next` 为相对路径（非 `//`）或与 `ISSUER` 同源的 http(s) 绝对地址时跟随，否则回退自身首页。
- [ ] **Step 2: 重建 demo 容器并 curl 实测**：`GET /demo/logout?next=http%3A%2F%2Flocalhost%2Flogin` → `Location: http://localhost/login`；`next=https://evil.example` → `Location: /demo/`。
- [ ] **Step 3: 提交**：`fix: 演示站登出跟随同源绝对 next，修复串跳漏斗断链`

### Task 10: 前端 GuestOnly 绝对 next 与注册文案

**Files:**
- Modify: `frontend/src/components/GuestOnly.tsx`
- Modify: `frontend/src/pages/RegisterPage.tsx`（toast 文案）
- Test: `frontend/src/__tests__/GuestOnly.test.tsx`（新增 1 测试）

- [ ] **Step 1: 写失败测试**：`/login?next=http://localhost/oauth2/authorize` 已登录时断言 `window.location.replace` 被调用。
- [ ] **Step 2: 运行确认失败**：`npx vitest run src/__tests__/GuestOnly.test.tsx`。
- [ ] **Step 3: 最小实现**：安全绝对 URL 走 `window.location.replace`；相对 URL 保持 `<Navigate>`。
- [ ] **Step 4: 运行确认通过**。
- [ ] **Step 5: 提交**：`fix: 已登录访问登录页时正确恢复绝对同源 next 跳转，注册成功文案对齐后端语义`

### Task 11: 文档与 CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`（未发布区：破坏性变更/安全加固/行为变更/缺陷修复/运维工具）
- Modify: `docs/deployment.md`（环境变量表：UVICORN_WORKERS 与 memory 存储说明）
- Modify: `docs/audit/2026-08-16-360-degree-review.md`（各条目标注「已修复」）

- [ ] **Step 1: 更新三份文档**。
- [ ] **Step 2: 提交**：`docs: 记录第二轮审查修复与迁移说明`

### 收尾验证

- [ ] `cd backend && .venv/bin/python -m pytest -q` 全绿。
- [ ] `cd frontend && npx tsc -b && npm run lint && npm test -- --run && npm run build` 全绿。
- [ ] 真 PG：`alembic downgrade -1 && alembic upgrade head` 往返。
- [ ] `docker compose --profile bundle --profile demo up -d --build` 重建后健康检查 + 关键 curl 复测。
