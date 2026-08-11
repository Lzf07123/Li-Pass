# 里程碑 3：用户中心与网站级访问控制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完善用户中心（资料/密码/手机绑定/设备会话管理/应用广场），并实现网站级账号黑名单：门户管理后台与网站自助 API 均可封禁账号，`authorize / token / userinfo` 三层强制拦截。

**Architecture:** 新增 `client_user_blocks` 表并给 `oauth_clients` 增加 `home_url`；黑名单校验收敛到 `app/services/blocks.py`，在 OIDC 三个端点与授权确认 approve 处调用；网站自助 API 用 HTTP Basic（client_id + client_secret）鉴权；前端扩展用户中心页与应用管理页。

**Tech Stack:** 沿用里程碑 1-2（FastAPI/SQLAlchemy/React/Vite/Docker Compose），无新增第三方依赖。

## Global Constraints

- Python >=3.11；测试用 SQLite 内存库；沿用 `client`/`db_session`/`captured_email` 夹具与 `tests/helpers.py`。
- 黑名单按 `(client_id, user_id)` 或 `(client_id, email)` 判重；email 全小写；同一网站对同一账号不得重复封禁。
- 三层拦截：`authorize`（有会话时）命中黑名单 → 302 回 `redirect_uri` 带 `error=access_denied&error_description=account_blocked`；`token` 命中 → 403；`userinfo` 命中 → 403；授权确认 `approve` 命中 → 403。
- 网站自助 API 仅限机密客户端（有 client_secret），Basic 鉴权；公开客户端返回 401。
- 用户中心：`PUT /api/v1/me`、`POST /api/v1/me/password`（改密后踢出其他会话）、`POST /api/v1/me/phone/bind`（演示模式直接标记已验证）、`GET/DELETE /api/v1/sessions`（不能删除当前会话）、`GET /api/v1/apps`（已同意且未被拉黑的启用应用）。
- 时间戳一律 `DateTime(timezone=True)`；比较用 `_as_utc`；TDD；每个任务一个独立 commit；测试产物保持 gitignore。
- 本里程碑采用“当前会话内联执行”（用户已确认）：控制器按 TDD 实现并提交，审查采用控制器直接核对。

---

### Task 1: 黑名单模型、home_url 与迁移

**Files:**
- Create: `backend/app/models/client_user_block.py`
- Modify: `backend/app/models/oauth_client.py`（追加 `home_url`）
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas/oauth.py`（`ClientCreate/ClientUpdate/ClientOut` 追加 `home_url`）
- Create: `backend/tests/test_client_user_block.py`

**Interfaces:**
- Consumes: `OAuthClient`、`User`、`Base`。
- Produces: `ClientUserBlock`（`client_id/user_id/email/reason/created_at`）；`OAuthClient.home_url`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_client_user_block.py`：

```python
from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.models.user import User


def test_create_block(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"], home_url="http://x")
    db_session.add_all([user, client])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(client)

    block = ClientUserBlock(client_id=client.id, user_id=user.id, email=user.email, reason="滥用")
    db_session.add(block)
    db_session.commit()
    assert block.id is not None
    assert client.home_url == "http://x"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_client_user_block.py -v`

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现模型与 schema**

`backend/app/models/client_user_block.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClientUserBlock(Base):
    __tablename__ = "client_user_blocks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/oauth_client.py` 的 `OAuthClient` 追加：

```python
    home_url: Mapped[str | None] = mapped_column(String(500))
```

`backend/app/models/__init__.py` 追加导出 `ClientUserBlock`。

`backend/app/schemas/oauth.py` 的 `ClientCreate`/`ClientUpdate`/`ClientOut` 与 `serialize_client` 追加 `home_url`：

```python
# ClientCreate / ClientUpdate
    home_url: str | None = Field(default=None, max_length=500)
# ClientOut
    home_url: str | None
# serialize_client
        "home_url": client.home_url,
```

- [ ] **Step 4: 运行测试确认通过，生成迁移并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_client_user_block.py -v`

Expected: PASS（1 passed）。

Run:

```bash
alembic revision --autogenerate -m "add client user blocks and home url"
alembic upgrade head
```

确认迁移包含 `client_user_blocks` 表与 `oauth_clients.home_url` 列后提交：

```bash
git add backend
git commit -m "feat: 添加网站账号黑名单模型与 home_url"
```

---

### Task 2: 黑名单服务与三层拦截

**Files:**
- Create: `backend/app/services/blocks.py`
- Modify: `backend/app/services/oidc.py`（`redirect_error` 增加 `error_description`）
- Modify: `backend/app/api/routes/oidc.py`（authorize/token/userinfo 三层拦截）
- Modify: `backend/app/api/routes/consent.py`（approve 拦截）
- Create: `backend/tests/test_blocks_enforcement.py`

**Interfaces:**
- Consumes: `ClientUserBlock`、`User`、`OAuthClient`。
- Produces: `find_block(db, client_id, user) -> ClientUserBlock | None`；`list_blocks(db, client_id) -> list`；`add_block(db, client, *, email=None, user_id=None, reason="") -> ClientUserBlock`（重复或缺失目标抛 `ValueError`）；`remove_block(db, block_id) -> None`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_blocks_enforcement.py`：

```python
from app.models.user_consent import UserConsent
from sqlalchemy import select

from app.models.user import User
from tests.helpers import authorize_params, create_client, register_and_login


def block_user(db_session, client_model, user, email=None) -> None:
    from app.models.client_user_block import ClientUserBlock

    db_session.add(
        ClientUserBlock(
            client_id=client_model.id,
            user_id=user.id if user else None,
            email=email or (user.email if user else None),
            reason="滥用",
        )
    )
    db_session.commit()


def test_authorize_blocked_user_gets_access_denied(client, captured_email, db_session) -> None:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    block_user(db_session, client_model, user)

    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert "error=access_denied" in location
    assert "error_description=account_blocked" in location


def test_userinfo_blocked_after_token(client, captured_email, db_session) -> None:
    from urllib.parse import parse_qs, urlparse

    from app.security.jwt import decode_token
    from tests.helpers import TEST_VERIFIER

    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid", "profile"]))
    db_session.commit()
    response = client.get("/oauth2/authorize", params=authorize_params())
    code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    token_response = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": TEST_VERIFIER,
        },
    )
    access = token_response.json()["access_token"]
    assert client.get("/oauth2/userinfo", headers={"Authorization": f"Bearer {access}"}).status_code == 200

    block_user(db_session, client_model, user)
    response = client.get("/oauth2/userinfo", headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 403


def test_token_blocked(client, captured_email, db_session) -> None:
    from urllib.parse import parse_qs, urlparse

    from tests.helpers import TEST_VERIFIER

    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid"]))
    db_session.commit()
    response = client.get("/oauth2/authorize", params=authorize_params())
    code = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    block_user(db_session, client_model, user)
    response = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": TEST_VERIFIER,
        },
    )
    assert response.status_code == 403
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_blocks_enforcement.py -v`

Expected: FAIL（模块不存在/未拦截）。

- [ ] **Step 3: 实现黑名单服务**

`backend/app/services/blocks.py`：

```python
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.client_user_block import ClientUserBlock


def find_block(db: Session, client_id, user) -> ClientUserBlock | None:
    return db.scalar(
        select(ClientUserBlock).where(
            ClientUserBlock.client_id == client_id,
            or_(
                ClientUserBlock.user_id == user.id,
                ClientUserBlock.email == user.email,
            ),
        )
    )


def list_blocks(db: Session, client_id) -> list[ClientUserBlock]:
    return list(
        db.scalars(
            select(ClientUserBlock)
            .where(ClientUserBlock.client_id == client_id)
            .order_by(ClientUserBlock.created_at.desc())
        ).all()
    )


def add_block(
    db: Session,
    client,
    *,
    email: str | None = None,
    user_id=None,
    reason: str = "",
) -> ClientUserBlock:
    if not email and user_id is None:
        raise ValueError("email 或 user_id 至少填一项")
    if email:
        email = email.lower()
        existing = db.scalar(
            select(ClientUserBlock).where(
                ClientUserBlock.client_id == client.id,
                ClientUserBlock.email == email,
            )
        )
    else:
        existing = db.scalar(
            select(ClientUserBlock).where(
                ClientUserBlock.client_id == client.id,
                ClientUserBlock.user_id == user_id,
            )
        )
    if existing is not None:
        raise ValueError("该账号已被此网站封禁")
    block = ClientUserBlock(
        client_id=client.id,
        user_id=user_id,
        email=email,
        reason=reason,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def remove_block(db: Session, block_id) -> None:
    block = db.get(ClientUserBlock, block_id)
    if block is None:
        raise ValueError("封禁记录不存在")
    db.delete(block)
    db.commit()
```

`backend/app/services/oidc.py` 的 `redirect_error` 改为：

```python
def redirect_error(
    redirect_uri: str,
    error: str,
    state: str | None = None,
    error_description: str | None = None,
) -> str:
    params = {"error": error}
    if state:
        params["state"] = state
    if error_description:
        params["error_description"] = error_description
    return f"{redirect_uri}?{urlencode(params)}"
```

- [ ] **Step 4: 接入三层拦截**

`backend/app/api/routes/oidc.py`：

- authorize：`user = get_optional_user(...)` 之后、consent 查询之前插入：

```python
    if user is not None and find_block(db, client.id, user) is not None:
        return RedirectResponse(
            redirect_error(
                redirect_uri,
                "access_denied",
                state,
                "account_blocked",
            ),
            status_code=302,
        )
```

- token：`user` 校验 active 之后、签发之前插入：

```python
    if find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")
```

- userinfo：`user` 校验 active 之后插入：

```python
    client = db.scalar(
        select(OAuthClient).where(OAuthClient.client_id == claims["client_id"])
    )
    if client is not None and find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")
```

`backend/app/api/routes/consent.py` 的 `approve` 在查到 `client` 后插入：

```python
    if find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")
```

相应文件顶部补 import：`from app.services.blocks import find_block`。

- [ ] **Step 5: 运行测试确认通过并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_blocks_enforcement.py -v && .venv/bin/python -m pytest tests/ -q`

Expected: 新增 3 passed，全量全绿。提交：

```bash
git add backend
git commit -m "feat: 网站账号黑名单三层拦截"
```

---

### Task 3: 网站自助黑名单 API

**Files:**
- Create: `backend/app/api/routes/client_blocks.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_client_blocks_api.py`

**Interfaces:**
- Consumes: `add_block`/`list_blocks`/`remove_block`。
- Produces: `GET /oauth2/client/blocks`、`POST /oauth2/client/blocks`、`DELETE /oauth2/client/blocks/{block_id}`（HTTP Basic 鉴权，仅机密客户端）。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_client_blocks_api.py`：

```python
import base64

from app.models.oauth_client import OAuthClient
from app.security.tokens import hash_token


def auth_header(client_id: str, secret: str) -> dict:
    token = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_public_client_rejected(client, db_session) -> None:
    db_session.add(
        OAuthClient(client_id="cli_pub", name="Pub", redirect_uris=["http://x/cb"])
    )
    db_session.commit()
    response = client.get("/oauth2/client/blocks", headers=auth_header("cli_pub", "x"))
    assert response.status_code == 401


def test_confidential_client_crud(client, db_session) -> None:
    db_session.add(
        OAuthClient(
            client_id="cli_conf",
            client_secret_hash=hash_token("secret123"),
            name="Conf",
            redirect_uris=["http://x/cb"],
        )
    )
    db_session.commit()
    headers = auth_header("cli_conf", "secret123")

    response = client.post(
        "/oauth2/client/blocks",
        headers=headers,
        json={"email": "Bad@Example.com", "reason": "滥用"},
    )
    assert response.status_code == 200
    block_id = response.json()["id"]
    assert response.json()["email"] == "bad@example.com"

    response = client.post(
        "/oauth2/client/blocks",
        headers=headers,
        json={"email": "bad@example.com"},
    )
    assert response.status_code == 409

    response = client.get("/oauth2/client/blocks", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.delete(f"/oauth2/client/blocks/{block_id}", headers=headers)
    assert response.status_code == 204
    assert client.get("/oauth2/client/blocks", headers=headers).json() == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_client_blocks_api.py -v`

Expected: FAIL（404）。

- [ ] **Step 3: 实现路由**

`backend/app/api/routes/client_blocks.py`：

```python
import base64
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.schemas.oauth import ClientBlockCreate, ClientBlockOut
from app.security.tokens import hash_token
from app.services.blocks import add_block, list_blocks, remove_block

router = APIRouter(prefix="/oauth2/client", tags=["client-blocks"])


def _auth_client(authorization: str, db: Session) -> OAuthClient:
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    try:
        raw = base64.b64decode(authorization.removeprefix("Basic ")).decode()
        client_id, client_secret = raw.split(":", 1)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if (
        client is None
        or client.client_secret_hash is None
        or not client.is_active
        or hash_token(client_secret) != client.client_secret_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    return client


@router.get("/blocks", response_model=list[dict])
def list_client_blocks(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    client = _auth_client(authorization or "", db)
    return [_serialize(b) for b in list_blocks(db, client.id)]


@router.post("/blocks", response_model=dict)
def create_client_block(
    payload: ClientBlockCreate,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    client = _auth_client(authorization or "", db)
    try:
        block = add_block(
            db,
            client,
            email=payload.email,
            user_id=uuid.UUID(payload.user_id) if payload.user_id else None,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _serialize(block)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_block(
    block_id,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> None:
    client = _auth_client(authorization or "", db)
    block = db.get(ClientUserBlock, block_id)
    if block is None or block.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "封禁记录不存在")
    remove_block(db, block.id)


def _serialize(block) -> dict:
    return {
        "id": str(block.id),
        "user_id": str(block.user_id) if block.user_id else None,
        "email": block.email,
        "reason": block.reason,
        "created_at": block.created_at,
    }
```

说明：`ClientBlockCreate`/`ClientBlockOut` 加入 `backend/app/schemas/oauth.py`：

```python
class ClientBlockCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    user_id: str | None = None
    reason: str = Field(default="", max_length=500)


class ClientBlockOut(BaseModel):
    id: str
    user_id: str | None
    email: str | None
    reason: str
    created_at: datetime
```

`backend/app/main.py` 注册 `client_blocks_routes.router`。

- [ ] **Step 4: 运行测试确认通过并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_client_blocks_api.py -v && .venv/bin/python -m pytest tests/ -q`

Expected: 新增 2 passed，全量全绿。提交：

```bash
git add backend
git commit -m "feat: 网站自助黑名单 API（Basic 鉴权）"
```

---

### Task 4: 管理端黑名单 API 与用户中心 API

**Files:**
- Modify: `backend/app/api/deps.py`（追加 `get_current_session`）
- Modify: `backend/app/api/routes/admin_clients.py`（黑名单 CRUD）
- Modify: `backend/app/schemas/auth.py`（资料/密码/手机/session/app 相关 schema）
- Modify: `backend/app/api/routes/users.py`（资料/密码/手机/会话/应用广场）
- Modify: `backend/app/main.py`（如需要新路由）
- Create: `backend/tests/test_user_center.py`
- Create: `backend/tests/test_admin_blocks.py`

**Interfaces:**
- Consumes: `get_current_user`、`get_current_admin`、`add_block`/`list_blocks`/`remove_block`。
- Produces: `PUT /api/v1/me`、`POST /api/v1/me/password`、`POST /api/v1/me/phone/bind`、`GET /api/v1/sessions`、`DELETE /api/v1/sessions/{id}`、`GET /api/v1/apps`；管理端 `GET/POST /api/v1/admin/clients/{id}/blocks`、`DELETE /api/v1/admin/clients/{id}/blocks/{block_id}`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_user_center.py`：

```python
from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.passwords import verify_password
from tests.helpers import create_client, register_and_login


def test_update_profile_and_password(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    response = client.put("/api/v1/me", json={"nickname": "NewName", "avatar_url": "http://a.png"})
    assert response.status_code == 200
    assert response.json()["nickname"] == "NewName"

    response = client.post(
        "/api/v1/me/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert response.status_code == 200
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert verify_password("newpassword456", user.password_hash)


def test_phone_bind_demo(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.post("/api/v1/me/phone/bind", json={"phone": "+8613800000000"})
    assert response.status_code == 200
    assert response.json()["phone"] == "+8613800000000"


def test_sessions_list_and_revoke(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.get("/api/v1/sessions")
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    current_id = sessions[0]["id"]
    response = client.delete(f"/api/v1/sessions/{current_id}")
    assert response.status_code == 400

    # 第二个会话
    client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "password123"})
    sessions = client.get("/api/v1/sessions").json()
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/v1/sessions/{other['id']}").status_code == 204
    assert len(client.get("/api/v1/sessions").json()) == 1


def test_apps_plaza_lists_consented(client, captured_email, db_session) -> None:
    client_model = create_client(db_session, home_url="http://localhost:3001")
    register_and_login(client, captured_email)
    assert client.get("/api/v1/apps").json() == []

    from app.models.user_consent import UserConsent
    from sqlalchemy import select

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid"]))
    db_session.commit()

    apps = client.get("/api/v1/apps").json()
    assert len(apps) == 1
    assert apps[0]["client_id"] == "cli_demo"
    assert apps[0]["home_url"] == "http://localhost:3001"
```

`backend/tests/test_admin_blocks.py`：

```python
from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password


def login_admin(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            nickname="Admin",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )


def test_admin_blocks_crud(client, db_session) -> None:
    login_admin(client, db_session)
    client_model = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add(client_model)
    db_session.commit()
    db_session.refresh(client_model)

    response = client.post(
        f"/api/v1/admin/clients/{client_model.id}/blocks",
        json={"email": "Bad@Example.com", "reason": "滥用"},
    )
    assert response.status_code == 200
    block_id = response.json()["id"]
    assert response.json()["email"] == "bad@example.com"

    assert len(client.get(f"/api/v1/admin/clients/{client_model.id}/blocks").json()) == 1
    assert (
        client.delete(f"/api/v1/admin/clients/{client_model.id}/blocks/{block_id}").status_code
        == 204
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_user_center.py tests/test_admin_blocks.py -v`

Expected: FAIL（404/未实现）。

- [ ] **Step 3: 实现依赖与会话工具**

`backend/app/api/deps.py` 重构为：

```python
def get_current_session(request: Request, db: Session = Depends(get_db)) -> SessionModel:
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    session = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    )
    now = datetime.now(timezone.utc)
    if (
        session is None
        or session.revoked_at is not None
        or _as_utc(session.expires_at) < now
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")
    session.last_used_at = now
    db.commit()
    return session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session = get_current_session(request, db)
    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User unavailable")
    return user
```

`backend/app/schemas/auth.py` 追加：

```python
from datetime import datetime


class ProfileUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=80)
    avatar_url: str | None = Field(default=None, max_length=500)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class PhoneBind(BaseModel):
    phone: str = Field(pattern=r"^\+?[0-9]{6,20}$")


class SessionOut(BaseModel):
    id: str
    device_name: str
    ip: str
    user_agent: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    current: bool


class AppOut(BaseModel):
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None
```

- [ ] **Step 4: 实现用户中心与管理员黑名单路由**

`backend/app/api/routes/users.py` 追加（补 import：`datetime/timezone`、`HTTPException/status`、`SessionModel`、`UserConsent`、`OAuthClient`、`find_block`、`verify_password`/`hash_password`、`get_current_session`、相关 schema）：

```python
@router.put("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    db.commit()
    return serialize_user(user)


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    current = get_current_session(request, db)
    others = db.scalars(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.id != current.id,
            SessionModel.revoked_at.is_(None),
        )
    ).all()
    for session in others:
        session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "密码已修改，其他会话已退出"}


@router.post("/me/phone/bind", response_model=UserOut)
def bind_phone(
    payload: PhoneBind,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user.phone = payload.phone
    user.phone_verified_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_user(user)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    current = get_current_session(request, db)
    sessions = db.scalars(
        select(SessionModel)
        .where(SessionModel.user_id == user.id)
        .order_by(SessionModel.created_at.desc())
    ).all()
    return [
        {
            "id": str(s.id),
            "device_name": s.device_name,
            "ip": s.ip,
            "user_agent": s.user_agent,
            "created_at": s.created_at,
            "last_used_at": s.last_used_at,
            "expires_at": s.expires_at,
            "current": s.id == current.id,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = db.get(SessionModel, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    current = get_current_session(request, db)
    if session.id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能退出当前会话")
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/apps", response_model=list[AppOut])
def list_apps(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    consents = db.scalars(
        select(UserConsent).where(UserConsent.user_id == user.id)
    ).all()
    client_ids = [c.client_id for c in consents]
    if not client_ids:
        return []
    clients = db.scalars(
        select(OAuthClient).where(
            OAuthClient.id.in_(client_ids), OAuthClient.is_active.is_(True)
        )
    ).all()
    result = []
    for client in clients:
        if find_block(db, client.id, user) is not None:
            continue
        result.append(
            {
                "client_id": client.client_id,
                "name": client.name,
                "description": client.description,
                "logo_url": client.logo_url,
                "home_url": client.home_url,
            }
        )
    return result
```

`backend/app/api/routes/admin_clients.py` 追加（补 import：`uuid`、`ClientUserBlock`、`ClientBlockCreate`、`add_block`/`list_blocks`/`remove_block`）：

```python
@router.get("/{client_id:uuid}/blocks", response_model=list[dict])
def admin_list_blocks(client_id, db: Session = Depends(get_db)) -> list[dict]:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return [_serialize_block(b) for b in list_blocks(db, client.id)]


@router.post("/{client_id:uuid}/blocks", response_model=dict)
def admin_add_block(
    client_id,
    payload: ClientBlockCreate,
    db: Session = Depends(get_db),
) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    try:
        block = add_block(
            db,
            client,
            email=payload.email,
            user_id=uuid.UUID(payload.user_id) if payload.user_id else None,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    return _serialize_block(block)


@router.delete("/{client_id:uuid}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_remove_block(client_id, block_id, db: Session = Depends(get_db)) -> None:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    block = db.get(ClientUserBlock, block_id)
    if block is None or block.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "封禁记录不存在")
    remove_block(db, block.id)


def _serialize_block(block) -> dict:
    return {
        "id": str(block.id),
        "user_id": str(block.user_id) if block.user_id else None,
        "email": block.email,
        "reason": block.reason,
        "created_at": block.created_at,
    }
```

`backend/app/schemas/oauth.py` 的 `ClientBlockCreate` 同时供两个路由使用。

- [ ] **Step 5: 运行测试确认通过并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_user_center.py tests/test_admin_blocks.py -v && .venv/bin/python -m pytest tests/ -q`

Expected: 新增 6 passed，全量全绿。提交：

```bash
git add backend
git commit -m "feat: 用户中心 API 与管理端黑名单 API"
```

---

### Task 5: 前端用户中心、应用广场与黑名单管理

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/AdminClientsPage.tsx`
- Create: `frontend/src/__tests__/DashboardPage.test.tsx`
- Modify: `frontend/src/__tests__/AdminClientsPage.test.tsx`

**Interfaces:**
- Consumes: 后端 Task 4 的全部 API。
- Produces: 用户中心（资料/密码/手机/会话/应用广场）、管理页黑名单区；前端测试通过。

- [ ] **Step 1: 编写失败测试**

`frontend/src/__tests__/DashboardPage.test.tsx`：

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DashboardPage } from "../pages/DashboardPage";

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染用户信息与应用广场", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            id: "1",
            email: "a@example.com",
            nickname: "Alice",
            email_verified: true,
            role: "user",
            status: "active",
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify([
            { client_id: "cli_demo", name: "Demo", description: "", logo_url: null, home_url: "http://localhost:3001" },
          ]),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Alice")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
  });
});
```

`frontend/src/__tests__/AdminClientsPage.test.tsx` 追加黑名单用例：fetch 依次返回客户端列表（含 id）与黑名单列表，断言黑名单邮箱渲染。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test`

Expected: FAIL（页面未实现）。

- [ ] **Step 3: 实现类型与 API**

`frontend/src/api/types.ts` 追加：

```ts
export interface SessionOut {
  id: string;
  device_name: string;
  ip: string;
  user_agent: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  current: boolean;
}

export interface AppOut {
  client_id: string;
  name: string;
  description: string;
  logo_url: string | null;
  home_url: string | null;
}

export interface ClientBlockOut {
  id: string;
  user_id: string | null;
  email: string | null;
  reason: string;
  created_at: string;
}
```

`frontend/src/api/client.ts` 追加：

```ts
import type { AppOut, ClientBlockOut, SessionOut } from "./types";

export const meApi = {
  updateProfile: (data: { nickname?: string; avatar_url?: string | null }) =>
    api<UserOut>("/api/v1/me", { method: "PUT", body: JSON.stringify(data) }),
  changePassword: (data: { current_password: string; new_password: string }) =>
    api<{ message: string }>("/api/v1/me/password", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  bindPhone: (data: { phone: string }) =>
    api<UserOut>("/api/v1/me/phone/bind", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

export const sessionsApi = {
  list: () => api<SessionOut[]>("/api/v1/sessions"),
  revoke: (id: string) => api<void>(`/api/v1/sessions/${id}`, { method: "DELETE" }),
};

export const appsApi = {
  list: () => api<AppOut[]>("/api/v1/apps"),
};

export const adminBlocksApi = {
  list: (clientId: string) => api<ClientBlockOut[]>(`/api/v1/admin/clients/${clientId}/blocks`),
  add: (clientId: string, data: { email: string; reason: string }) =>
    api<ClientBlockOut>(`/api/v1/admin/clients/${clientId}/blocks`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  remove: (clientId: string, blockId: string) =>
    api<void>(`/api/v1/admin/clients/${clientId}/blocks/${blockId}`, {
      method: "DELETE",
    }),
};
```

- [ ] **Step 4: 实现页面**

`frontend/src/pages/DashboardPage.tsx` 改为分区布局：资料编辑（昵称/头像）、修改密码、绑定手机、设备会话列表（含“退出此设备”按钮，当前会话禁用）、应用广场（卡片 + “进入”链接指向 `home_url`）。

关键数据加载：

```ts
const [user, setUser] = useState<UserOut | null>(null);
const [apps, setApps] = useState<AppOut[]>([]);
const [sessions, setSessions] = useState<SessionOut[]>([]);

useEffect(() => {
  authApi.me().then(setUser).catch(() => navigate("/login"));
  appsApi.list().then(setApps).catch(() => undefined);
  sessionsApi.list().then(setSessions).catch(() => undefined);
}, [navigate]);
```

`frontend/src/pages/AdminClientsPage.tsx`：创建表单增加 `home_url` 输入；每个客户端卡片增加“黑名单”区（`adminBlocksApi.list(client.id)` 渲染邮箱/原因，输入邮箱+原因添加，删除按钮）。

- [ ] **Step 5: 运行测试与构建并提交**

Run: `cd frontend && npm run test && npm run build`

Expected: PASS + 构建成功。提交：

```bash
git add frontend
git commit -m "feat: 前端用户中心、应用广场与黑名单管理"
```

---

### Task 6: 种子更新、端到端验证与合并

**Files:**
- Modify: `backend/scripts/seed_demo_client.py`（`home_url`）
- Modify: `README.md`
- Modify: `.env.example`（如需要）

**Interfaces:**
- Consumes: 全部后端/前端改动。
- Produces: 端到端证据：应用广场、封禁三层拦截、网站自助 API、解封恢复。

- [ ] **Step 1: 更新种子脚本**

`backend/scripts/seed_demo_client.py` 的客户端创建/更新处追加 `home_url="http://localhost:3001"`。

- [ ] **Step 2: 全量测试**

Run:

```bash
cd backend && .venv/bin/python -m pytest -q
cd ../frontend && npm run test && npm run build
```

Expected: 后端全绿（预计 45+ passed）、前端全绿。

- [ ] **Step 3: 端到端验证**

重建容器后用以下流程验证（localhost 与 Docker 命令需要非沙箱权限）：

1. 注册/激活/登录新用户；从示例网站完成一次授权（应用广场出现 `demo-site`）。
2. 用 `make_admin` 提升该用户为管理员；用管理 API 创建机密客户端 `cli-e2e`，拿到 secret。
3. 网站自助 API：`POST /oauth2/client/blocks`（Basic 鉴权）封禁该用户邮箱 → 200。
4. 再次从示例网站登录（或直接 authorize）→ 302 带 `error=access_denied&error_description=account_blocked`。
5. 解封（DELETE）→ authorize 恢复（已同意过则直接发 code）→ token/userinfo 200。
6. 重新封禁后，用已有 access_token 调 `/oauth2/userinfo` → 403。

Expected: 全部符合。

- [ ] **Step 4: 更新 README 并提交**

`README.md` 功能特性补充“用户中心（资料/手机/设备会话/应用广场）”与“网站级账号黑名单（后台 + 自助 API）”，然后：

```bash
git add backend frontend README.md
git commit -m "docs: 里程碑 3 功能说明与种子更新"
```

- [ ] **Step 5: 合并回 main**

```bash
git checkout main
git merge <branch>
```

合并后在 main 上复跑后端/前端测试，再清理临时分支。

---

## 里程碑 3 完成标准

- 用户可修改资料/密码（改密后其他会话被踢出）、绑定手机（演示模式）、查看并远程退出设备会话；应用广场展示已同意且未被拉黑的启用应用。
- 后台与网站自助 API 均可封禁/解封账号；`authorize` 被拉黑账号返回 `error=access_denied`，`token`/`userinfo` 返回 403；解封后立即恢复。
- 后端 `pytest` 全绿；前端 `vitest` + 构建全绿；E2E 全部通过；`git status` 干净。
