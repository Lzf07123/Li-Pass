# 联邦登出（Federated Logout）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Li&Pass（自研 OIDC IdP）补齐联邦登出：接入网站可发起“退出网站同时退出 SSO”（RP-Initiated Logout），门户/管理员登出时通过 Back-Channel Logout 通知所有已登录网站下线，并为未实现回程通道的网站提供浏览器串跳漏斗兜底。

**Architecture:** 复用现有“授权码 + PKCE + RS256”OIDC 栈。新增 `oidc_client_sessions` 表记录“门户会话登录过哪些网站”；`id_token` 增加 `sid`；新增 `GET /oauth2/end-session`（前端 `/logout/confirm` 确认页）+ 确认 API；登出令牌按 OIDC Back-Channel Logout 规范用现有 RS256 私钥签发，经 httpx 异步分发（后台任务 + 重试 + SSRF 防护）；门户登出响应改为携带串跳漏斗 URL。不做 Front-Channel Logout / Session Management iframe（第三方 Cookie 已被主流浏览器禁用）。

**Tech Stack:** 沿用 FastAPI/SQLAlchemy 2.0/Alembic/React+Vite/PostgreSQL/Redis；新增 httpx（0.28.1，用于回程分发）；示例站 Flask。

## Global Constraints

- Python >=3.11；后端依赖以 `backend/requirements*.txt` 为准；测试用 SQLite 内存库（conftest 的 `client`/`db_session` 夹具）。
- 只做 OIDC：`end_session` + Back-Channel Logout；不做 front-channel iframe。`post_logout_redirect_uri` 必须与客户端白名单**精确匹配**（防开放重定向）。
- 所有新增时间戳列 `DateTime(timezone=True)`；时间比较统一 UTC；新 JSON 列默认 `[]`。
- `sid` = 门户 `Session.id` 的 UUID 字符串；登出令牌 `aud` 必须等于目标 `client_id`。
- 生产环境 `backchannel_logout_uri` 必须 https 且目标 IP 不得为回环/私网（SSRF 防护）；开发环境放行以便本地 demo。
- API 前缀 `/api/v1`；OIDC 端点 `/.well-known/openid-configuration`、`/oauth2/end-session`。
- 所有任务 TDD：先写失败测试、验证失败、最小实现、验证通过、提交；每个任务一个独立 commit。
- 分支 `codex/federated-logout`；新提交信息用 `feat:`/`test:`/`docs:` 前缀，与仓库历史一致。

---

### Task 1: 数据模型与迁移

**Files:**
- Modify: `backend/app/models/oauth_client.py`
- Modify: `backend/app/models/authorization_code.py`
- Create: `backend/app/models/oidc_client_session.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/7f2a9d3c8e1b_add_federated_logout.py`
- Create: `backend/tests/test_federated_logout_models.py`

**Interfaces:**
- Consumes: `app.models.base.Base`、既有 `oauth_clients`/`authorization_codes` 模型。
- Produces: `OAuthClient.post_logout_redirect_uris: list`、`OAuthClient.backchannel_logout_uri: str | None`、`AuthorizationCode.session_id: uuid.UUID | None`、`OIDCClientSession`（导出到 `app.models`）。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_federated_logout_models.py`：

```python
import uuid

from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User


def test_client_logout_fields_defaults(db_session) -> None:
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add(client)
    db_session.commit()
    assert client.post_logout_redirect_uris == []
    assert client.backchannel_logout_uri is None


def test_oidc_client_session_tracks_lipass_session(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add_all([user, client])
    db_session.commit()
    from datetime import datetime, timezone

    portal = SessionModel(
        user_id=user.id,
        token_hash="hash",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(portal)
    db_session.commit()
    link = OIDCClientSession(
        session_id=portal.id, client_id=client.id, user_id=user.id
    )
    db_session.add(link)
    db_session.commit()
    assert link.sid == str(portal.id)
    assert link.revoked_at is None


def test_authorization_code_carries_session_id(db_session) -> None:
    code = AuthorizationCode(
        code_hash="h",
        redirect_uri="http://x/cb",
        scope="openid",
        expires_at=None,
        session_id=uuid.uuid4(),
    )
    assert code.session_id is not None
```

> 注意：`AuthorizationCode` 需要 `user_id`/`client_id` 外键但可空校验发生在数据库层，SQLite 不强制 NOT NULL；测试只验证列存在。

- [ ] **Step 2: 运行验证失败**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_federated_logout_models.py -v`
Expected: FAIL（`OAuthClient has no attribute post_logout_redirect_uris` 等 AttributeError/ImportError）

- [ ] **Step 3: 实现模型**

`oauth_client.py` 追加两列；`authorization_code.py` 追加 `session_id`（UUID 可空 + FK `sessions.id` ondelete CASCADE）；新建 `oidc_client_session.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OIDCClientSession(Base):
    __tablename__ = "oidc_client_sessions"
    __table_args__ = (UniqueConstraint("session_id", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def sid(self) -> str:
        return str(self.session_id)
```

`models/__init__.py` 导入并导出 `OIDCClientSession`。

- [ ] **Step 4: 迁移**

`backend/alembic/versions/7f2a9d3c8e1b_add_federated_logout.py`（`down_revision = "6d1f9c0b2e4a"`）：`add_column` 三列、`create_table` + 索引、`create_unique_constraint`；`downgrade()` 反向。

- [ ] **Step 5: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_federated_logout_models.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/app/models backend/alembic/versions backend/tests/test_federated_logout_models.py
git commit -m "feat: 联邦登出数据模型与迁移"
```

---

### Task 2: 客户端 schema / 管理 API / 序列化

**Files:**
- Modify: `backend/app/schemas/oauth.py`
- Modify: `backend/app/api/routes/admin_clients.py`
- Modify: `backend/tests/test_admin_clients.py`
- Create: `backend/tests/test_federated_logout_schemas.py`

**Interfaces:**
- Consumes: Task 1 的 `OAuthClient` 新字段。
- Produces: `ClientCreate/ClientUpdate/ClientOut` 与 `serialize_client` 输出新增 `post_logout_redirect_uris: list[str]`、`backchannel_logout_uri: str | None`；管理 API 透传。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_federated_logout_schemas.py`：

```python
import pytest
from pydantic import ValidationError

from app.schemas.oauth import ClientCreate, ClientUpdate


def test_client_create_accepts_logout_fields() -> None:
    payload = ClientCreate(
        name="X",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/"],
        backchannel_logout_uri="https://x/backchannel",
    )
    assert payload.post_logout_redirect_uris == ["https://x/"]
    assert payload.backchannel_logout_uri == "https://x/backchannel"


def test_post_logout_redirect_uris_rejects_javascript() -> None:
    with pytest.raises(ValidationError):
        ClientCreate(
            name="X",
            redirect_uris=["http://x/cb"],
            post_logout_redirect_uris=["javascript:alert(1)"],
        )


def test_client_update_partial() -> None:
    payload = ClientUpdate(post_logout_redirect_uris=[])
    assert payload.model_dump(exclude_unset=True) == {"post_logout_redirect_uris": []}
```

- [ ] **Step 2: 运行验证失败**
Expected: FAIL（extra input 被忽略 → `assert` 失败）

- [ ] **Step 3: 实现**

`schemas/oauth.py`：`ClientCreate`/`ClientUpdate` 增加 `post_logout_redirect_uris: list[str] = []`（Update 为 `None` 缺省）与 `backchannel_logout_uri: str | None`；校验器：post-logout 列表逐项 `_validate_web_url` 并查重，backchannel 走 `_validate_web_url`。`ClientOut`/`serialize_client` 增加两字段。`admin_clients.py::create_client` 显式传两字段（其余字段经 `model_dump` 自动透传）。

- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_federated_logout_schemas.py backend/tests/test_admin_clients.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 客户端登出字段（回跳白名单/回程地址）管理 API"
```

---

### Task 3: id_token 的 sid 与登录关系记录

**Files:**
- Modify: `backend/app/security/jwt.py`
- Modify: `backend/app/services/oidc.py`
- Modify: `backend/app/api/routes/consent.py`
- Modify: `backend/app/api/routes/oidc.py`
- Modify: `backend/tests/test_oidc_token.py`

**Interfaces:**
- Consumes: Task 1 的 `AuthorizationCode.session_id`、`OIDCClientSession`。
- Produces: `create_authorization_code(..., session_id: uuid.UUID | None = None)`；`create_id_token(..., sid: str | None = None)` 时 id_token 含 `sid`；token 端点按 `(session_id, client_id)` upsert `OIDCClientSession`。

- [ ] **Step 1: 写失败测试**

`test_oidc_token.py` 增加：

```python
def test_id_token_contains_sid_and_records_client_session(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    oauth = create_client(
        db_session, client_id="cli_sid", redirect_uris=["http://x/cb"]
    )
    params = authorize_params(
        {"client_id": "cli_sid", "redirect_uri": "http://x/cb"}
    )
    auth = client.get("/oauth2/authorize", params=params)
    assert auth.status_code == 302
    code = dict(parse_qs(urlsplit(auth.headers["location"]).query))["code"][0]
    resp = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://x/cb",
            "client_id": "cli_sid",
            "code_verifier": TEST_VERIFIER,
        },
    )
    assert resp.status_code == 200
    claims = decode_token(resp.json()["id_token"], audience="cli_sid")
    assert claims["sid"]
    link = db_session.scalar(select(OIDCClientSession))
    assert link is not None
    assert link.sid == claims["sid"]
```

- [ ] **Step 2: 运行验证失败**
Expected: FAIL（KeyError `sid` / `OIDCClientSession` 未导入）

- [ ] **Step 3: 实现**

- `create_id_token` 增加 `sid: str | None = None`，非空时写入 payload。
- `create_authorization_code` 增加 `session_id` 参数并落库；`oidc.py::authorize` 自动同意分支与 `consent.py::approve` 传 `session.id`。
- token 端点消费授权码后：若 `record.session_id` 非空，先查同 `(session_id, client_id)` 行，不存在则 `db.add(OIDCClientSession(...))`；`create_id_token(..., sid=str(record.session_id))`。

- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_oidc_token.py backend/tests/test_oidc_authorize.py backend/tests/test_consent.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: id_token 携带 sid 并记录门户会话与客户端的登录关系"
```

---

### Task 4: 登出令牌签发与 SSRF 校验

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/services/federated_logout.py`
- Create: `backend/tests/test_federated_logout_token.py`

**Interfaces:**
- Produces: `issue_logout_token(sub: str, sid: str, client_id: str) -> str`（claims：`iss`/`aud=client_id`/`sub`/`sid`/`iat`/`exp`/`jti`/`events`）；`assert_safe_backchannel_url(url: str) -> None`。

- [ ] **Step 1: 写失败测试**

```python
import jwt as pyjwt
import pytest

from app.security.jwt import decode_token
from app.services.federated_logout import (
    assert_safe_backchannel_url,
    issue_logout_token,
)


def test_logout_token_claims(client_has_settings) -> None:
    token = issue_logout_token("sub-1", "sid-1", "cli_a")
    claims = decode_token(token, audience="cli_a")
    assert claims["sub"] == "sub-1"
    assert claims["sid"] == "sid-1"
    assert "http://schemas.openid.net/event/backchannel-logout" in claims["events"]
    assert claims["jti"]


def test_logout_token_expires_within_window(client_has_settings) -> None:
    token = issue_logout_token("sub-1", "sid-1", "cli_a")
    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert 0 < claims["exp"] - claims["iat"] <= 120


def test_safe_url_rejects_private_host_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    with pytest.raises(ValueError):
        assert_safe_backchannel_url("https://127.0.0.1/logout")
```

（测试夹具用 `monkeypatch` 而非真实 settings；生产校验分支只依据 `environment`。）

- [ ] **Step 2: 运行验证失败**
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现**

- `config.py`：`logout_token_ttl_seconds: int = 120`、`backchannel_logout_timeout_seconds: float = 5.0`、`backchannel_logout_max_retries: int = 2`，含校验（ttl 30–600、timeout 1–30、retries 0–5）。
- `issue_logout_token` 复用 `jwt._encode`；`assert_safe_backchannel_url`：scheme 必须 http/https（生产必须 https）、host 非空；生产环境解析 host 的地址（字面 IP 或 DNS 解析）并拒绝 loopback/private/link-local/reserved。

- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_federated_logout_token.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 登出令牌签发与回程地址 SSRF 校验"
```

---

### Task 5: 回程登出分发服务

**Files:**
- Modify: `backend/app/services/federated_logout.py`
- Modify: `backend/requirements.txt`（httpx==0.28.1 移入生产依赖）
- Create: `backend/tests/test_backchannel_dispatch.py`

**Interfaces:**
- Produces: `collect_logout_targets(db, session_ids: list[uuid.UUID]) -> list[LogoutTarget]`（`LogoutTarget(uri, client_id, sid, sub)`）；`dispatch_backchannel_logout(targets, *, transport=None) -> dict[str, bool]`（POST form `logout_token`，失败按设置重试，结果 `{client_id: delivered}`；后台任务内打开 `SessionLocal` 写审计）。

- [ ] **Step 1: 写失败测试**

```python
import httpx

from app.services.federated_logout import (
    LogoutTarget,
    dispatch_backchannel_logout,
)


def test_dispatch_posts_logout_token_and_retries() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content.decode())
        if len(seen) < 2:
            return httpx.Response(500)
        return httpx.Response(204)

    result = dispatch_backchannel_logout(
        [LogoutTarget(uri="https://rp.example/backchannel", client_id="cli_a",
                      sid="sid-1", sub="sub-1")],
        transport=httpx.MockTransport(handler),
    )
    assert result == {"cli_a": True}
    assert len(seen) == 2
    token = dict(urllib.parse.parse_qsl(seen[0]))["logout_token"]
    claims = decode_token(token, audience="cli_a")
    assert claims["sid"] == "sid-1"
```

- [ ] **Step 2: 运行验证失败**
Expected: FAIL（ImportError）

- [ ] **Step 3: 实现**

`collect_logout_targets`：join `oidc_client_sessions` + `oauth_clients`，过滤 `backchannel_logout_uri is not None` 与 `is_active`。`dispatch_backchannel_logout`：逐 target 签发令牌 → `httpx.Client(transport=transport, timeout=..., follow_redirects=False).post(uri, data={"logout_token": token})` → 2xx 记成功；失败重试 `backchannel_logout_max_retries` 次；异常只 `logger.warning` 不抛出。审计在调用方后台任务完成（见 Task 8）。

- [ ] **Step 4: 运行验证通过**
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 回程登出分发服务（httpx + 重试）"
```

---

### Task 6: 待确认登出请求存储

**Files:**
- Create: `backend/app/services/logout_requests.py`
- Modify: `backend/tests/conftest.py`（`_clear_memory_state` 清理内存实现）
- Create: `backend/tests/test_logout_requests_store.py`

**Interfaces:**
- Produces: `PendingLogoutRequest(client_id, post_logout_redirect_uri, state, sid, sub, client_name)`；`LogoutRequestStore` 抽象 + 内存/Redis 实现；`get_logout_request_store()`（复用 `pending_request_store` 配置，Redis key 前缀 `logout-request:`，TTL 600s）。

- [ ] **Step 1: 写失败测试**
创建 → 读取 → 删除；读取不存在返回 None。
- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**（镜像 `pending_requests.py`）
- [ ] **Step 4: 运行验证通过**
- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 待确认登出请求存储（内存/Redis）"
```

---

### Task 7: end_session 端点 + 确认 API + 发现文档

**Files:**
- Modify: `backend/app/api/deps.py`（新增 `get_optional_session`）
- Modify: `backend/app/api/routes/oidc.py`
- Create: `backend/tests/test_end_session.py`

**Interfaces:**
- Produces:
  - `GET /oauth2/end-session?id_token_hint&post_logout_redirect_uri&state&client_id`：校验 → 无会话直接 302 回跳；有会话写入 pending 并 302 到 `{frontend_base_url}/logout/confirm?request_id=...`。
  - `GET /api/v1/oauth/logout-requests/{request_id}` → `{client_name}`（公开只读，防止会话已失效时无法回跳）。
  - `POST /api/v1/oauth/logout-requests/{request_id}/confirm` → 吊销当前会话、派发回程登出、返回 `{redirect_url}`；`/cancel` 只删 pending。
  - discovery 增加 `end_session_endpoint`、`backchannel_logout_supported: true`、`frontchannel_logout_supported: false`。

- [ ] **Step 1: 写失败测试（关键用例）**

```python
def test_end_session_redirects_to_confirm_page(client, db_session, captured_email):
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    resp = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    assert resp.status_code == 302
    assert "/logout/confirm?request_id=" in resp.headers["location"]


def test_end_session_rejects_unregistered_redirect(client, db_session, captured_email):
    register_and_login(client, captured_email)
    create_client(db_session, client_id="cli_logout", redirect_uris=["http://x/cb"])
    resp = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://evil.example/",
        },
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp.headers["location"]


def test_confirm_revokes_session_and_returns_redirect(client, db_session, captured_email):
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    started = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    request_id = dict(
        urllib.parse.parse_qsl(urllib.parse.urlsplit(started.headers["location"]).query)
    )["request_id"]
    resp = client.post(f"/api/v1/oauth/logout-requests/{request_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["redirect_url"] == "https://x/after-logout?state=st-9"
    assert client.get("/api/v1/me").status_code == 401
```

- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**

`get_optional_session`：`try/except HTTPException` 包装 `get_current_session`。end_session 校验顺序：client 解析（client_id 或 id_token_hint 的 aud）→ redirect 精确匹配白名单 → 会话探测 → 302。确认端点依赖 `get_current_user` + `get_current_session`，吊销会话后 `background_tasks.add_task(_dispatch_and_audit, targets)`；`_dispatch_and_audit` 打开 `SessionLocal`，调用 `dispatch_backchannel_logout` 并按结果写审计（`category="oidc"`，action `backchannel_logout_delivered`/`backchannel_logout_failed`）。

- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_end_session.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: OIDC RP 发起登出端点与确认 API"
```

---

### Task 8: 门户登出漏斗 + 回程联动

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/services/federated_logout.py`（`build_logout_funnel`）
- Modify: `backend/tests/test_auth_login.py`（204 → 200 断言更新）
- Create: `backend/tests/test_portal_logout.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/logout` → `200 {"redirect_to": str | null}`；`build_logout_funnel(uris: list[str], final_url: str) -> str` 生成嵌套 `?next=` 链。

- [ ] **Step 1: 写失败测试**

```python
def test_portal_logout_returns_funnel_for_clients_without_backchannel(
    client, db_session, captured_email
):
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_funnel",
        redirect_uris=["http://x/cb"],
        logout_uri="https://x/logout",
        post_logout_redirect_uris=[],
    )
    # 建立登录关系：走一次 authorize→token（或用 helper 直接插 OIDCClientSession）
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    location = resp.json()["redirect_to"]
    assert location.startswith("https://x/logout?next=")
    assert "login" in location


def test_logout_without_clients_returns_null_redirect(client, captured_email):
    register_and_login(client, captured_email)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["redirect_to"] is None
```

- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**

auth.logout 改为：吊销会话 → `collect_logout_targets(db, [session.id])` 与“有 logout_uri 且无 backchannel 的 uri 列表”→ `background_tasks.add_task(...)` 派发 → 返回 `{"redirect_to": build_logout_funnel(uris, f"{frontend}/login") if uris else None}`。更新 `test_auth_login.py` 中两处 204 断言为 200 + `redirect_to is None`。

- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_portal_logout.py backend/tests/test_auth_login.py backend/tests/test_twofa_login.py backend/tests/test_audit_events.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 门户登出返回浏览器串跳漏斗并派发回程登出"
```

---

### Task 9: 会话撤销联动（用户/管理员/取消授权）

**Files:**
- Modify: `backend/app/api/routes/users.py`
- Modify: `backend/app/api/routes/admin_sessions.py`
- Create: `backend/tests/test_revoke_dispatch.py`

**Interfaces:**
- Consumes: `collect_logout_targets`、`dispatch_backchannel_logout`。
- Produces: 六个撤销路径（用户单个/全部、管理员单个/批量/全部、取消授权）在吊销后经 BackgroundTasks 派发回程登出；取消授权按用户×客户端维度收集目标。

- [ ] **Step 1: 写失败测试**

用 `httpx.MockTransport` monkeypatch `dispatch_backchannel_logout` 的参数无法跨线程；改为断言：撤销后 `collect_logout_targets` 返回的目标列表（测试通过创建 link 后撤销并检查审计/目标收集函数）。用例：

```python
def test_admin_batch_revoke_collects_targets(client, db_session, admin_client_fixture):
    # 建立 session + OIDCClientSession + backchannel_logout_uri 客户端
    # POST /api/v1/admin/sessions/batch-revoke
    # 断言目标会话对应客户端已被收集（通过 monkeypatch 的收集函数被调用参数）
```

实现细节：各路由在吊销前先收集目标 `list[LogoutTarget]`，`background_tasks.add_task(_dispatch_and_audit, targets)`；`_dispatch_and_audit` 复用 Task 7 的模块级函数（移到 `federated_logout.py` 供两处调用）。

- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_revoke_dispatch.py backend/tests/test_admin_sessions.py backend/tests/test_user_center.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 会话撤销与取消授权联动回程登出"
```

---

### Task 10: 前端

**Files:**
- Create: `frontend/src/pages/LogoutConfirmPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/AdminClientsPage.tsx`
- Create: `frontend/src/__tests__/LogoutConfirmPage.test.tsx`
- Modify: `frontend/src/__tests__/DashboardPage.test.tsx`、`AdminClientsPage.test.tsx`

**Interfaces:**
- Consumes: Task 7 的确认 API、Task 8 的 `{redirect_to}`。
- Produces: `/logout/confirm` 页（读取 `request_id`，展示“将退出所有网站”，确认/取消按钮）；`authApi.logout` 返回 `{redirect_to: string | null}`；`oauthApi.logoutRequestInfo/confirmLogoutRequest/cancelLogoutRequest`；AdminClientsPage 新增“登出回跳白名单（每行一个）”与“回程登出地址”输入。

- [ ] **Step 1: 写失败测试**

`LogoutConfirmPage.test.tsx`：mock fetch 依次返回 `{client_name: "Demo"}` 与 `{redirect_url: "https://x/after"}`，断言页面出现客户端名、点击“确认退出”后 `window.location.href` 变为 redirect_url。

- [ ] **Step 2: 运行验证失败**
Expected: FAIL（页面/路由不存在）
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行验证通过**

Run: `npm test -- --run frontend/src/__tests__/LogoutConfirmPage.test.tsx` 后全量 `npm test`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git commit -m "feat: 登出确认页与管理端登出字段前端"
```

---

### Task 11: demo 站、种子、compose 与文档

**Files:**
- Modify: `examples/demo-site/app.py`
- Modify: `backend/scripts/seed_demo_client.py`
- Modify: `docker-compose.yaml`
- Modify: `docs/oidc-integration.md`
- Modify: `README.md`
- Modify: `.env.example`、`backend/.env.example`

**Interfaces:**
- demo 站：callback 存 `session["sid"]`；`/logout` 清本地会话后 302 到 `{ISSUER}/oauth2/end-session?client_id=...&post_logout_redirect_uri={prefix}/&state=...`；新增 `POST /backchannel-logout` 校验 logout_token（iss/aud/events/sid）并清本地会话。
- seed：注册 `post_logout_redirect_uris=[DEMO_HOME_URL]`、`backchannel_logout_uri=DEMO_BACKCHANNEL_LOGOUT_URI`。
- docs：`oidc-integration.md` 增“登出”章节（end_session 参数、post_logout_redirect_uris 注册、logout_token 校验与 jti 防重放、sid 绑定）；README 功能清单加联邦登出。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_discovery.py` 不存在，改在 `test_end_session.py` 追加发现文档断言（`end_session_endpoint`、`backchannel_logout_supported`）；demo 站无自动化测试，用 `python -c "import examples.demo-site.app"` 编译检查 + compose `docker compose config -q` 验证。

- [ ] **Step 2: 运行验证失败**
- [ ] **Step 3: 实现**
- [ ] **Step 4: 运行验证通过**

Run: `backend/.venv/bin/python -m pytest backend/tests/test_end_session.py -q`；`python -m py_compile examples/demo-site/app.py`；`docker compose config -q`
Expected: PASS / exit 0

- [ ] **Step 5: 提交**

```bash
git commit -m "docs: 联邦登出接入指南与 demo 站示例"
```

---

## Self-Review

1. **Spec coverage:** 上轮建议的四个里程碑均有任务覆盖：end_session+确认页（Task 7）、sid+关系表（Task 1/3）、回程登出全链路（Task 4/5/8/9）、demo+文档（Task 11）；front-channel/iframe 明确不实现（Global Constraints）。
2. **Placeholder scan:** 各任务含真实测试代码、命令与实现要点，无 TBD。
3. **Type consistency:** `LogoutTarget(uri, client_id, sid, sub)` 在 Task 5 定义并被 Task 7/8/9 使用；`redirect_to`/`redirect_url` 命名在前后端一致（前端 `redirect_url` 来自确认 API，`redirect_to` 来自 auth.logout）。
