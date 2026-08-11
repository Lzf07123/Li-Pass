# 里程碑 2：OIDC 核心流程 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现统一登录门户的 OIDC/OAuth2 授权码 + PKCE 核心流程：授权网站管理（管理 API）、`authorize / token / userinfo / jwks / discovery` 端点、授权确认页（自动捕获门户会话并询问用户）、同意记录复用，以及一个可本地演示的示例授权网站。

**Architecture:** 在既有 FastAPI 后端上新增 `oauth_clients`、`authorization_codes`、`user_consents` 表；JWT 用 RS256 非对称签名（私钥文件首次启动生成）；待授权请求存 Redis（测试用内存实现）；前端新增 `/consent` 授权确认页与 `/admin/clients` 应用管理页；`examples/demo-site/` 提供 Flask 示例网站。

**Tech Stack:** 沿用里程碑 1（FastAPI/SQLAlchemy/Alembic/React/Vite/PostgreSQL/Redis），新增 PyJWT、cryptography、redis-py；示例网站用 Flask + requests。

## Global Constraints

- Python >=3.11；后端依赖以 `backend/requirements*.txt` 为准；测试用 SQLite 内存库（conftest 已提供 `client`/`db_session`/`engine` 夹具）。
- 仓库内不内置反向代理；前端经 `VITE_API_BASE_URL` 直连后端；示例网站独立端口 3001，不经过任何反代。
- 仅支持授权码流程（`response_type=code`）+ PKCE（`S256`），不实现隐式流程；`redirect_uri` 必须精确匹配白名单。
- 授权码一次性、10 分钟过期、存 SHA-256 哈希并绑定 client/redirect_uri/PKCE；access token 为 RS256 JWT（15 分钟）不落库；client_secret 只存 SHA-256 哈希；id_token 携带 `nonce` 与 `acr`。
- 门户会话 Cookie 沿用里程碑 1（HttpOnly、Secure/SameSite 由配置控制）；OIDC 端点只信任门户会话，不共享跨站 Cookie。
- 管理 API 仅限 `role=admin` 用户访问；通过 `backend/scripts/make_admin.py` 提升管理员。
- 邮箱全小写存储；密码 Argon2id；所有新增时间戳列必须 `DateTime(timezone=True)`；比较时间统一 UTC（沿用 `_as_utc` 归一化模式）。
- API 前缀 `/api/v1`；OIDC 标准端点路径：`/.well-known/openid-configuration`、`/oauth2/authorize`、`/oauth2/token`、`/oauth2/userinfo`、`/oauth2/jwks`。
- 所有任务采用 TDD：先写失败测试，再实现，再提交；每个任务一个独立 commit。
- 子代理实现时禁止再派发子代理，禁止使用 deepseek-v4-pro（当前不可用）。

---

### Task 1: OAuth 数据模型与迁移

**Files:**
- Create: `backend/app/models/oauth_client.py`
- Create: `backend/app/models/authorization_code.py`
- Create: `backend/app/models/user_consent.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_oauth_models.py`

**Interfaces:**
- Consumes: `app.models.base.Base`、`users` 表（Task 1/2 里程碑 1）。
- Produces: 模型 `OAuthClient`、`AuthorizationCode`、`UserConsent`（字段与约束见下），全部导出到 `app.models`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_oauth_models.py`：

```python
from datetime import datetime, timezone

from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent


def test_create_oauth_models(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client = OAuthClient(
        client_id="cli_test",
        client_secret_hash="secret-hash",
        name="Demo Site",
        redirect_uris=["http://localhost:3001/callback"],
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    assert client.is_active is True
    assert "openid" in client.scopes
    assert client.id is not None

    code = AuthorizationCode(
        code_hash="code-hash",
        client_id=client.id,
        user_id=user.id,
        redirect_uri="http://localhost:3001/callback",
        scope="openid",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(code)
    db_session.commit()
    assert code.id is not None

    consent = UserConsent(user_id=user.id, client_id=client.id, scopes=["openid"])
    db_session.add(consent)
    db_session.commit()
    assert consent.id is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oauth_models.py -v`

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现模型**

`backend/app/models/oauth_client.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OAuthClient(Base):
    __tablename__ = "oauth_clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    client_secret_hash: Mapped[str | None] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500), default="")
    logo_url: Mapped[str | None] = mapped_column(String(500))
    redirect_uris: Mapped[list] = mapped_column(JSON, default=list)
    scopes: Mapped[list] = mapped_column(
        JSON, default=lambda: ["openid", "profile", "email"]
    )
    require_consent_every_time: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`backend/app/models/authorization_code.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuthorizationCode(Base):
    __tablename__ = "authorization_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    redirect_uri: Mapped[str] = mapped_column(String(1000))
    scope: Mapped[str] = mapped_column(String(500))
    nonce: Mapped[str | None] = mapped_column(String(255))
    code_challenge: Mapped[str | None] = mapped_column(String(255))
    code_challenge_method: Mapped[str] = mapped_column(String(10), default="S256")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/user_consent.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserConsent(Base):
    __tablename__ = "user_consents"
    __table_args__ = (UniqueConstraint("user_id", "client_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("oauth_clients.id", ondelete="CASCADE"), index=True
    )
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

`backend/app/models/__init__.py` 追加导出：

```python
from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.user_consent import UserConsent
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oauth_models.py -v`

Expected: PASS（1 passed）。

- [ ] **Step 5: 生成迁移并提交**

Run:

```bash
cd backend
alembic revision --autogenerate -m "create oauth clients codes consents"
```

确认迁移包含 `oauth_clients`、`authorization_codes`、`user_consents` 三张表及唯一约束 `uq_user_consents_user_id` 后提交：

```bash
git add backend
git commit -m "feat: 添加 OAuth 客户端/授权码/同意记录模型与迁移"
```

---

### Task 2: JWT/密钥服务与配置扩展

**Files:**
- Modify: `backend/app/core/config.py`
- Create: `backend/app/security/jwt.py`
- Create: `backend/tests/test_jwt.py`
- Modify: `.gitignore`（忽略 `jwt_private.pem`）
- Modify: `backend/tests/conftest.py`（顶部设置测试私钥路径）

**Interfaces:**
- Consumes: `get_settings()`。
- Produces: `create_access_token(user, client_id, scope) -> str`；`create_id_token(user, client_id, nonce, scope) -> str`；`decode_token(token, audience=None) -> dict`；`public_jwks() -> dict`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_jwt.py`：

```python
import jwt as pyjwt

from app.core.config import get_settings
from app.security.jwt import (
    create_access_token,
    create_id_token,
    decode_token,
    public_jwks,
)


class FakeUser:
    id = "00000000-0000-0000-0000-000000000001"
    email = "a@example.com"
    nickname = "Alice"
    email_verified_at = None


def test_access_token_roundtrip() -> None:
    token = create_access_token(FakeUser(), "cli_demo", "openid profile email")
    claims = decode_token(token, audience="cli_demo")
    assert claims["sub"] == FakeUser.id
    assert claims["aud"] == "cli_demo"
    assert claims["scope"] == "openid profile email"


def test_access_token_wrong_audience_fails() -> None:
    token = create_access_token(FakeUser(), "cli_demo", "openid")
    try:
        decode_token(token, audience="cli_other")
        raise AssertionError("should have raised")
    except pyjwt.InvalidAudienceError:
        pass


def test_id_token_has_nonce_and_acr() -> None:
    token = create_id_token(FakeUser(), "cli_demo", "nonce-123", "openid")
    claims = decode_token(token, audience="cli_demo")
    assert claims["nonce"] == "nonce-123"
    assert claims["acr"] == "urn:portal-oss:acr:1fa"
    assert claims["email"] == "a@example.com"


def test_jwks_contains_rs256_key() -> None:
    jwks = public_jwks()
    assert jwks["keys"][0]["alg"] == "RS256"
    assert jwks["keys"][0]["kty"] == "RSA"
    assert jwks["keys"][0]["kid"] == "portal-rs256-1"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_jwt.py -v`

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 扩展配置**

`backend/app/core/config.py` 的 `Settings` 追加：

```python
    jwt_issuer: str = "http://localhost:8000"
    jwt_private_key_path: str = "jwt_private.pem"
    oauth_access_token_ttl_minutes: int = 15
    oauth_id_token_ttl_minutes: int = 5
    oauth_code_ttl_minutes: int = 10
    pending_request_store: str = "memory"
```

`.gitignore` 追加：

```text
# JWT 私钥
jwt_private.pem
```

`backend/tests/conftest.py` 顶部（所有 `app` 导入之前）追加：

```python
import os
import tempfile

os.environ.setdefault(
    "JWT_PRIVATE_KEY_PATH", os.path.join(tempfile.gettempdir(), "portal-test-jwt.pem")
)
```

- [ ] **Step 4: 实现 JWT 服务**

`backend/app/security/jwt.py`：

```python
import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings

KID = "portal-rs256-1"


@lru_cache
def _load_key_pair(path: str) -> tuple[object, object]:
    key_path = Path(path)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_path.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        key_path.chmod(0o600)
    private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    return private_key, private_key.public_key()


def _b64(number: int) -> str:
    size = max(1, (number.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(number.to_bytes(size, "big")).rstrip(b"=").decode()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    settings = get_settings()
    private_key, _ = _load_key_pair(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


def create_access_token(user, client_id: str, scope: str) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user.id),
        "aud": client_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.oauth_access_token_ttl_minutes),
        "scope": scope,
        "client_id": client_id,
    }
    return _encode(payload)


def create_id_token(user, client_id: str, nonce: str | None, scope: str) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user.id),
        "aud": client_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.oauth_id_token_ttl_minutes),
        "nonce": nonce,
        "acr": "urn:portal-oss:acr:1fa",
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "nickname": user.nickname,
        "name": user.nickname,
        "scope": scope,
    }
    return _encode(payload)


def decode_token(token: str, audience: str | None = None) -> dict:
    settings = get_settings()
    _, public_key = _load_key_pair(settings.jwt_private_key_path)
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=audience,
        options={"verify_aud": audience is not None},
    )


def public_jwks() -> dict:
    settings = get_settings()
    _, public_key = _load_key_pair(settings.jwt_private_key_path)
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64(numbers.n),
                "e": _b64(numbers.e),
            }
        ]
    }
```

`backend/requirements.txt` 追加依赖：

```text
PyJWT==2.10.1
cryptography==44.0.0
redis==5.2.1
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_jwt.py -v`

Expected: PASS（4 passed）。测试首次运行会生成临时私钥文件（`/tmp/portal-test-jwt.pem`）。

- [ ] **Step 6: 提交**

```bash
git add backend .gitignore
git commit -m "feat: 添加 RS256 JWT 服务与配置"
```

---

### Task 3: 待授权请求存储（内存 + Redis）

**Files:**
- Create: `backend/app/services/pending_requests.py`
- Create: `backend/tests/test_pending_requests.py`

**Interfaces:**
- Consumes: `get_settings()`（`redis_url`、`pending_request_store`）。
- Produces: `PendingAuthRequest` dataclass（`client_id/redirect_uri/scope/state/nonce/code_challenge/code_challenge_method`）；`PendingRequestStore`（`create/get/delete`）；`get_pending_request_store() -> PendingRequestStore`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_pending_requests.py`：

```python
from app.services.pending_requests import (
    InMemoryPendingRequestStore,
    PendingAuthRequest,
)


def make_request() -> PendingAuthRequest:
    return PendingAuthRequest(
        client_id="cli_demo",
        redirect_uri="http://localhost:3001/callback",
        scope="openid profile",
        state="state-1",
        nonce="nonce-1",
        code_challenge="challenge",
        code_challenge_method="S256",
    )


def test_inmemory_create_get_delete() -> None:
    store = InMemoryPendingRequestStore()
    request_id = store.create(make_request())
    assert store.get(request_id) == make_request()
    store.delete(request_id)
    assert store.get(request_id) is None


def test_inmemory_expired_request_returns_none() -> None:
    from datetime import datetime, timedelta, timezone

    store = InMemoryPendingRequestStore()
    request_id = store.create(make_request())
    item = store._items[request_id]
    store._items[request_id] = (
        item[0],
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert store.get(request_id) is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pending_requests.py -v`

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现存储**

`backend/app/services/pending_requests.py`：

```python
import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import redis

from app.core.config import get_settings


@dataclass
class PendingAuthRequest:
    client_id: str
    redirect_uri: str
    scope: str
    state: str | None = None
    nonce: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str = "S256"


class PendingRequestStore:
    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        raise NotImplementedError

    def get(self, request_id: str) -> PendingAuthRequest | None:
        raise NotImplementedError

    def delete(self, request_id: str) -> None:
        raise NotImplementedError


class InMemoryPendingRequestStore(PendingRequestStore):
    def __init__(self) -> None:
        self._items: dict[str, tuple[PendingAuthRequest, datetime]] = {}

    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        request_id = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._items[request_id] = (request, expires)
        return request_id

    def get(self, request_id: str) -> PendingAuthRequest | None:
        item = self._items.get(request_id)
        if item is None:
            return None
        request, expires = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(request_id, None)
            return None
        return request

    def delete(self, request_id: str) -> None:
        self._items.pop(request_id, None)


class RedisPendingRequestStore(PendingRequestStore):
    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def _key(self, request_id: str) -> str:
        return f"pending-auth:{request_id}"

    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        request_id = secrets.token_urlsafe(24)
        self._client.setex(
            self._key(request_id), ttl_seconds, json.dumps(asdict(request))
        )
        return request_id

    def get(self, request_id: str) -> PendingAuthRequest | None:
        raw = self._client.get(self._key(request_id))
        if raw is None:
            return None
        return PendingAuthRequest(**json.loads(raw))

    def delete(self, request_id: str) -> None:
        self._client.delete(self._key(request_id))


def get_pending_request_store() -> PendingRequestStore:
    settings = get_settings()
    if settings.pending_request_store == "memory":
        return _memory_store
    if settings.pending_request_store == "redis":
        global _redis_store
        if _redis_store is None:
            _redis_store = RedisPendingRequestStore(
                redis.Redis.from_url(settings.redis_url, decode_responses=True)
            )
        return _redis_store
    raise ValueError(f"Unsupported pending request store: {settings.pending_request_store}")


_memory_store = InMemoryPendingRequestStore()
_redis_store: RedisPendingRequestStore | None = None
```

说明：`get_pending_request_store()` 必须返回进程内单例，否则每次调用新建内存存储会导致 authorize 写入的待授权请求在 consent 读取时丢失（Task 5 与 Task 6 之间跨请求共享状态）。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_pending_requests.py -v`

Expected: PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 添加待授权请求存储（内存 + Redis）"
```

---

### Task 4: 管理 API（应用 CRUD）与管理员脚本

**Files:**
- Modify: `backend/app/security/tokens.py`（追加 `generate_client_id`/`generate_client_secret`）
- Modify: `backend/app/api/deps.py`（追加 `get_current_admin`）
- Create: `backend/app/schemas/oauth.py`
- Create: `backend/app/api/routes/admin_clients.py`
- Modify: `backend/app/main.py`
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/make_admin.py`
- Create: `backend/tests/test_admin_clients.py`

**Interfaces:**
- Consumes: `get_current_user`、`UserRole`、`hash_token`。
- Produces: `get_current_admin(user) -> User`；`POST /api/v1/admin/clients`、`GET /api/v1/admin/clients`、`GET/PATCH/DELETE /api/v1/admin/clients/{id}`、`POST /api/v1/admin/clients/{id}/reset-secret`；`ClientSecretOut` 返回一次性明文 secret。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_admin_clients.py`：

```python
from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_token


def login_as(client, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_admin_required(client, db_session) -> None:
    db_session.add(
        User(
            email="u@example.com",
            password_hash=hash_password("password123"),
            nickname="U",
            role=UserRole.user,
        )
    )
    db_session.commit()
    assert login_as(client, "u@example.com").status_code == 200
    response = client.get("/api/v1/admin/clients")
    assert response.status_code == 403


def test_admin_create_and_reset_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    assert login_as(client, "a@example.com").status_code == 200

    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Demo",
            "redirect_uris": ["http://localhost:3001/callback"],
            "public": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    secret = body["client_secret"]
    assert secret
    stored = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == body["client"]["client_id"])
    )
    assert stored is not None
    assert stored.client_secret_hash == hash_token(secret)

    response = client.post(f"/api/v1/admin/clients/{body['client']['id']}/reset-secret")
    assert response.status_code == 200
    new_secret = response.json()["client_secret"]
    assert new_secret != secret


def test_public_client_has_no_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "SPA",
            "redirect_uris": ["http://localhost:5173/callback"],
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["client_secret"] is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_clients.py -v`

Expected: FAIL（404/导入错误）。

- [ ] **Step 3: 实现工具、依赖与路由**

`backend/app/security/tokens.py` 追加：

```python
def generate_client_id() -> str:
    return "cli_" + secrets.token_urlsafe(24)


def generate_client_secret() -> str:
    return secrets.token_urlsafe(48)
```

`backend/app/api/deps.py` 追加：

```python
def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user
```

`backend/app/schemas/oauth.py`：

```python
from datetime import datetime

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] = Field(min_length=1)
    scopes: list[str] = Field(default=["openid", "profile", "email"])
    require_consent_every_time: bool = False
    public: bool = True


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] | None = None
    scopes: list[str] | None = None
    require_consent_every_time: bool | None = None
    is_active: bool | None = None


class ClientOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str
    logo_url: str | None
    redirect_uris: list[str]
    scopes: list[str]
    require_consent_every_time: bool
    is_active: bool
    created_at: datetime


class ClientSecretOut(BaseModel):
    client: ClientOut
    client_secret: str | None


def serialize_client(client) -> dict:
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "name": client.name,
        "description": client.description,
        "logo_url": client.logo_url,
        "redirect_uris": client.redirect_uris,
        "scopes": client.scopes,
        "require_consent_every_time": client.require_consent_every_time,
        "is_active": client.is_active,
        "created_at": client.created_at,
    }
```

`backend/app/api/routes/admin_clients.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.schemas.oauth import (
    ClientCreate,
    ClientSecretOut,
    ClientUpdate,
    serialize_client,
)
from app.security.tokens import generate_client_id, generate_client_secret, hash_token

router = APIRouter(
    prefix="/api/v1/admin/clients",
    tags=["admin-clients"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[dict])
def list_clients(db: Session = Depends(get_db)) -> list[dict]:
    clients = db.scalars(
        select(OAuthClient).order_by(OAuthClient.created_at.desc())
    ).all()
    return [serialize_client(c) for c in clients]


@router.post("", response_model=ClientSecretOut)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> dict:
    client_secret = None
    client_secret_hash = None
    if not payload.public:
        client_secret = generate_client_secret()
        client_secret_hash = hash_token(client_secret)
    client = OAuthClient(
        client_id=generate_client_id(),
        client_secret_hash=client_secret_hash,
        name=payload.name,
        description=payload.description,
        logo_url=payload.logo_url,
        redirect_uris=payload.redirect_uris,
        scopes=payload.scopes,
        require_consent_every_time=payload.require_consent_every_time,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"client": serialize_client(client), "client_secret": client_secret}


@router.get("/{client_id:uuid}", response_model=dict)
def get_client(client_id, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return serialize_client(client)


@router.patch("/{client_id:uuid}", response_model=dict)
def update_client(client_id, payload: ClientUpdate, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return serialize_client(client)


@router.delete("/{client_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id, db: Session = Depends(get_db)) -> None:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    db.delete(client)
    db.commit()


@router.post("/{client_id:uuid}/reset-secret", response_model=ClientSecretOut)
def reset_secret(client_id, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    if client.client_secret_hash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "公开客户端没有密钥")
    client_secret = generate_client_secret()
    client.client_secret_hash = hash_token(client_secret)
    db.commit()
    return {"client": serialize_client(client), "client_secret": client_secret}
```

`backend/app/main.py` 注册路由：

```python
from app.api.routes import admin_clients as admin_clients_routes
...
app.include_router(admin_clients_routes.router)
```

`backend/scripts/make_admin.py`：

```python
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.user import User, UserRole


def main(email: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        if user is None:
            print(f"用户不存在: {email}")
            sys.exit(1)
        user.role = UserRole.admin
        db.commit()
        print(f"已将 {email} 设为管理员")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python -m scripts.make_admin <email>")
        sys.exit(2)
    main(sys.argv[1])
```

`backend/scripts/__init__.py` 为空文件。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_clients.py -v`

Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 应用管理 API 与管理员脚本"
```

---

### Task 5: OIDC authorize 端点

**Files:**
- Modify: `backend/app/api/deps.py`（追加 `get_optional_user`）
- Modify: `backend/tests/conftest.py`（`TestClient(app, follow_redirects=False)`，避免 302 被自动跟随）
- Create: `backend/app/services/oidc.py`
- Create: `backend/app/api/routes/oidc.py`
- Create: `backend/tests/helpers.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_oidc_authorize.py`

**Interfaces:**
- Consumes: `PendingAuthRequest`/`get_pending_request_store`（Task 3）、`OAuthClient`/`UserConsent`（Task 1）、`get_current_user`。
- Produces: `GET /oauth2/authorize`；`app.services.oidc.create_authorization_code(db, user, client, redirect_uri, scope, nonce, code_challenge, code_challenge_method) -> str`；`redirect_error(redirect_uri, error, state)`；`build_authorize_redirect(redirect_uri, code, state)`；`verify_pkce(code_verifier, code_challenge) -> bool`；`app.api.deps.get_optional_user(request, db) -> User | None`。

- [ ] **Step 1: 编写失败测试与测试助手**

`backend/tests/helpers.py`（供本任务及 Task 6/7 共用）：

```python
import base64
import hashlib

from app.models.oauth_client import OAuthClient

TEST_VERIFIER = "v" * 43


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def register_and_login(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )


def create_client(db_session, **overrides) -> OAuthClient:
    values = {
        "client_id": "cli_demo",
        "name": "Demo",
        "redirect_uris": ["http://localhost:3001/callback"],
        "scopes": ["openid", "profile", "email"],
    }
    values.update(overrides)
    client = OAuthClient(**values)
    db_session.add(client)
    db_session.commit()
    return client


def authorize_params(overrides=None) -> dict:
    params = {
        "response_type": "code",
        "client_id": "cli_demo",
        "redirect_uri": "http://localhost:3001/callback",
        "scope": "openid profile",
        "state": "st-1",
        "nonce": "n-1",
        "code_challenge": challenge_for(TEST_VERIFIER),
        "code_challenge_method": "S256",
    }
    if overrides:
        params.update(overrides)
    return params
```

`backend/tests/test_oidc_authorize.py`：

```python
from sqlalchemy import select

from app.models.user import User
from app.models.user_consent import UserConsent

from tests.helpers import authorize_params, create_client, register_and_login


def test_authorize_without_session_redirects_to_login(client, db_session) -> None:
    create_client(db_session)
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    assert response.headers["location"].startswith("/login?next=")


def test_authorize_with_session_redirects_to_consent(client, db_session, captured_email) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    assert "/consent?request_id=" in response.headers["location"]


def test_authorize_with_existing_consent_auto_approves(client, db_session, captured_email) -> None:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(
        select(User).where(User.email == "a@example.com")
    )
    db_session.add(
        UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid", "profile"])
    )
    db_session.commit()
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:3001/callback?code=")
    assert "state=st-1" in location


def test_authorize_invalid_redirect_uri(client, db_session) -> None:
    create_client(db_session)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"redirect_uri": "http://evil.example/cb"}),
    )
    assert response.status_code == 302
    assert response.headers["location"].startswith("/?error=invalid_redirect_uri")


def test_authorize_requires_pkce(client, db_session, captured_email) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"code_challenge": None}),
    )
    assert response.status_code == 302
    assert "error=invalid_request" in response.headers["location"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oidc_authorize.py -v`

Expected: FAIL（404/导入错误）。

- [ ] **Step 3: 实现 OIDC 服务与 authorize 端点**

`backend/app/api/deps.py` 追加：

```python
def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None
```

`backend/app/services/oidc.py`：

```python
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.authorization_code import AuthorizationCode
from app.security.tokens import hash_token


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def redirect_error(redirect_uri: str, error: str, state: str | None = None) -> str:
    params = {"error": error}
    if state:
        params["state"] = state
    return f"{redirect_uri}?{urlencode(params)}"


def build_authorize_redirect(redirect_uri: str, code: str, state: str | None = None) -> str:
    params = {"code": code}
    if state:
        params["state"] = state
    return f"{redirect_uri}?{urlencode(params)}"


def verify_pkce(code_verifier: str, code_challenge: str | None) -> bool:
    if not code_challenge:
        return False
    digest = hashlib.sha256(code_verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(expected, code_challenge)


def create_authorization_code(
    db: Session,
    user,
    client,
    redirect_uri: str,
    scope: str,
    nonce: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str = "S256",
) -> str:
    settings = get_settings()
    code = secrets.token_urlsafe(32)
    db.add(
        AuthorizationCode(
            code_hash=hash_token(code),
            client_id=client.id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            scope=scope,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.oauth_code_ttl_minutes),
        )
    )
    db.commit()
    return code
```

`backend/app/api/routes/oidc.py`（本任务只实现 authorize；其余端点 Task 7 追加）：

```python
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.user_consent import UserConsent
from app.services.oidc import (
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
)
from app.services.pending_requests import PendingAuthRequest, get_pending_request_store

router = APIRouter(tags=["oidc"])


@router.get("/oauth2/authorize")
def authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    scope: str | None = Query(None),
    state: str | None = Query(None),
    nonce: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str = Query("S256"),
    db: Session = Depends(get_db),
):
    if response_type != "code":
        return RedirectResponse("/?error=unsupported_response_type", status_code=302)

    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        return RedirectResponse("/?error=unauthorized_client", status_code=302)
    if redirect_uri not in client.redirect_uris:
        return RedirectResponse("/?error=invalid_redirect_uri", status_code=302)

    requested = scope.split() if scope else list(client.scopes)
    if "openid" not in requested or not set(requested).issubset(set(client.scopes)):
        return RedirectResponse(
            redirect_error(redirect_uri, "invalid_scope", state), status_code=302
        )
    if not code_challenge or code_challenge_method != "S256":
        return RedirectResponse(
            redirect_error(redirect_uri, "invalid_request", state), status_code=302
        )

    user = get_optional_user(request, db)
    if user is None:
        next_url = f"/oauth2/authorize?{request.url.query}"
        return RedirectResponse(f"/login?next={quote(next_url, safe='')}", status_code=302)

    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    scope_ok = consent is not None and set(requested).issubset(set(consent.scopes))
    if scope_ok and not client.require_consent_every_time:
        code = create_authorization_code(
            db,
            user,
            client,
            redirect_uri,
            " ".join(requested),
            nonce,
            code_challenge,
            code_challenge_method,
        )
        return RedirectResponse(
            build_authorize_redirect(redirect_uri, code, state), status_code=302
        )

    pending = PendingAuthRequest(
        client_id=client.client_id,
        redirect_uri=redirect_uri,
        scope=" ".join(requested),
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    request_id = get_pending_request_store().create(pending)
    return RedirectResponse(f"/consent?request_id={request_id}", status_code=302)
```

注意：所有 OIDC 重定向显式使用 `status_code=302`（新版 Starlette 的 `RedirectResponse` 默认 307）；conftest 的 `client` 夹具使用 `follow_redirects=False`，测试直接断言 302。

`backend/app/main.py` 注册：

```python
from app.api.routes import oidc as oidc_routes
...
app.include_router(oidc_routes.router)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oidc_authorize.py -v`

Expected: PASS（5 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 实现 OIDC authorize 端点（授权码 + PKCE 校验与授权确认跳转）"
```

---

### Task 6: 授权确认 API

**Files:**
- Create: `backend/app/api/routes/consent.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_consent.py`

**Interfaces:**
- Consumes: Task 5 的 `PendingAuthRequest`、`create_authorization_code`、`redirect_error`、`build_authorize_redirect`。
- Produces: `GET /api/v1/consent/{request_id}`、`POST /api/v1/consent/{request_id}/approve`、`POST /api/v1/consent/{request_id}/deny`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_consent.py`：

```python
from tests.helpers import authorize_params, create_client, register_and_login


def get_request_id(client, captured_email, db_session) -> str:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get("/oauth2/authorize", params=authorize_params())
    location = response.headers["location"]
    return location.split("request_id=")[1]


def test_consent_info_and_approve(client, captured_email, db_session) -> None:
    request_id = get_request_id(client, captured_email, db_session)
    response = client.get(f"/api/v1/consent/{request_id}")
    assert response.status_code == 200
    assert response.json()["client"]["name"] == "Demo"
    assert response.json()["scopes"] == ["openid", "profile"]

    response = client.post(f"/api/v1/consent/{request_id}/approve")
    assert response.status_code == 200
    redirect_url = response.json()["redirect_url"]
    assert redirect_url.startswith("http://localhost:3001/callback?code=")
    assert "state=st-1" in redirect_url

    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    assert "code=" in response.headers["location"]


def test_consent_deny(client, captured_email, db_session) -> None:
    request_id = get_request_id(client, captured_email, db_session)
    response = client.post(f"/api/v1/consent/{request_id}/deny")
    assert response.status_code == 200
    assert "error=access_denied" in response.json()["redirect_url"]
    assert "state=st-1" in response.json()["redirect_url"]


def test_consent_requires_session(client, db_session) -> None:
    create_client(db_session)
    response = client.get("/api/v1/consent/whatever")
    assert response.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_consent.py -v`

Expected: FAIL（404）。

- [ ] **Step 3: 实现授权确认路由**

`backend/app/api/routes/consent.py`：

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent
from app.services.oidc import (
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
)
from app.services.pending_requests import get_pending_request_store

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


def _get_pending_or_404(request_id: str):
    pending = get_pending_request_store().get(request_id)
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "授权请求不存在或已过期")
    return pending


@router.get("/{request_id}")
def consent_info(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    pending = _get_pending_or_404(request_id)
    client = db.scalar(
        select(OAuthClient).where(OAuthClient.client_id == pending.client_id)
    )
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return {
        "request_id": request_id,
        "client": {
            "name": client.name,
            "logo_url": client.logo_url,
            "description": client.description,
        },
        "scopes": pending.scope.split(),
    }


@router.post("/{request_id}/approve")
def approve(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    client = db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == pending.client_id, OAuthClient.is_active.is_(True)
        )
    )
    if client is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "应用不存在或已停用")

    code = create_authorization_code(
        db,
        user,
        client,
        pending.redirect_uri,
        pending.scope,
        pending.nonce,
        pending.code_challenge,
        pending.code_challenge_method,
    )
    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    granted = pending.scope.split()
    if consent is None:
        db.add(UserConsent(user_id=user.id, client_id=client.id, scopes=granted))
    else:
        consent.scopes = sorted(set(consent.scopes) | set(granted))
    db.commit()
    store.delete(request_id)
    return {"redirect_url": build_authorize_redirect(pending.redirect_uri, code, pending.state)}


@router.post("/{request_id}/deny")
def deny(
    request_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    store.delete(request_id)
    return {"redirect_url": redirect_error(pending.redirect_uri, "access_denied", pending.state)}
```

`backend/app/main.py` 注册 `consent_routes.router`。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_consent.py -v`

Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 实现授权确认 API（同意/拒绝与同意记录）"
```

---

### Task 7: token / userinfo / jwks / discovery 端点

**Files:**
- Modify: `backend/app/api/routes/oidc.py`
- Modify: `backend/app/services/oidc.py`（追加 `_as_utc`）
- Modify: `backend/requirements.txt`（追加 `python-multipart==0.0.20`，token 端点使用 Form 必须）
- Create: `backend/tests/test_oidc_token.py`

**Interfaces:**
- Consumes: Task 2 的 JWT 服务、Task 5 的 `verify_pkce`、`AuthorizationCode` 模型。
- Produces: `POST /oauth2/token`、`GET /oauth2/userinfo`、`GET /oauth2/jwks`、`GET /.well-known/openid-configuration`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_oidc_token.py`：

```python
from urllib.parse import parse_qs, urlparse

from app.security.jwt import decode_token
from tests.helpers import TEST_VERIFIER, authorize_params, create_client, register_and_login


def get_code(client, captured_email, db_session) -> str:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get("/oauth2/authorize", params=authorize_params())
    location = response.headers["location"]
    request_id = location.split("request_id=")[1]
    response = client.post(f"/api/v1/consent/{request_id}/approve")
    return parse_qs(urlparse(response.json()["redirect_url"]).query)["code"][0]


def exchange(client, code: str, verifier: str = TEST_VERIFIER) -> dict:
    return client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": verifier,
        },
    )


def test_token_and_userinfo_flow(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    response = exchange(client, code)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    access = body["access_token"]
    claims = decode_token(access, audience="cli_demo")
    assert claims["sub"]
    assert "openid" in claims["scope"]

    response = client.get(
        "/oauth2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "a@example.com"
    assert data["email_verified"] is True

    id_claims = decode_token(body["id_token"], audience="cli_demo")
    assert id_claims["nonce"] == "n-1"


def test_code_is_single_use(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    assert exchange(client, code).status_code == 200
    assert exchange(client, code).status_code == 400


def test_wrong_pkce_verifier_rejected(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    assert exchange(client, code, verifier="w" * 43).status_code == 400


def test_discovery_and_jwks(client) -> None:
    discovery = client.get("/.well-known/openid-configuration").json()
    assert discovery["issuer"] == "http://localhost:8000"
    assert discovery["response_types_supported"] == ["code"]
    jwks = client.get("/oauth2/jwks").json()
    assert jwks["keys"][0]["alg"] == "RS256"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oidc_token.py -v`

Expected: FAIL（404）。

- [ ] **Step 3: 实现四个端点**

在 `backend/app/api/routes/oidc.py` 文件顶部补 import：

```python
import uuid
from datetime import datetime, timezone

import jwt as pyjwt
from fastapi import Form, Header, HTTPException, status

from app.core.config import get_settings
from app.models.authorization_code import AuthorizationCode
from app.models.user import User, UserStatus
from app.security.jwt import (
    create_access_token,
    create_id_token,
    decode_token,
    public_jwks,
)
from app.security.tokens import hash_token
from app.services.oidc import _as_utc, verify_pkce
```

并在 `router` 定义之后追加四个端点：

```python
@router.get("/.well-known/openid-configuration")
def discovery() -> dict:
    settings = get_settings()
    base = settings.jwt_issuer
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth2/authorize",
        "token_endpoint": f"{base}/oauth2/token",
        "userinfo_endpoint": f"{base}/oauth2/userinfo",
        "jwks_uri": f"{base}/oauth2/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "code_challenge_methods_supported": ["S256"],
    }


@router.get("/oauth2/jwks")
def jwks() -> dict:
    return public_jwks()


@router.post("/oauth2/token")
def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    if grant_type != "authorization_code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported_grant_type")
    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_client")
    if client.client_secret_hash is not None:
        if not client_secret or hash_token(client_secret) != client.client_secret_hash:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")

    record = db.scalar(
        select(AuthorizationCode).where(
            AuthorizationCode.code_hash == hash_token(code or "")
        )
    )
    now = datetime.now(timezone.utc)
    if (
        record is None
        or record.client_id != client.id
        or record.redirect_uri != redirect_uri
        or record.consumed_at is not None
        or _as_utc(record.expires_at) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    if (
        client.client_secret_hash is None
        and not verify_pkce(code_verifier or "", record.code_challenge)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")

    record.consumed_at = now
    db.commit()
    user = db.get(User, record.user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")

    settings = get_settings()
    return {
        "access_token": create_access_token(user, client.client_id, record.scope),
        "token_type": "Bearer",
        "expires_in": settings.oauth_access_token_ttl_minutes * 60,
        "id_token": create_id_token(user, client.client_id, record.nonce, record.scope),
    }


@router.get("/oauth2/userinfo")
def userinfo(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    try:
        claims = decode_token(authorization.removeprefix("Bearer "))
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return {
        "sub": str(user.id),
        "email": user.email,
        "email_verified": user.email_verified_at is not None,
        "nickname": user.nickname,
        "name": user.nickname,
    }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_oidc_token.py -v`

Expected: PASS（4 passed）。

- [ ] **Step 5: 运行全量并提交**

Run: `cd backend && .venv/bin/python -m pytest -q`

Expected: 全绿。提交：

```bash
git add backend
git commit -m "feat: 实现 token/userinfo/jwks/discovery 端点"
```

---

### Task 8: 前端授权确认页与应用管理页

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/ConsentPage.tsx`
- Create: `frontend/src/pages/AdminClientsPage.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`（支持 `next` 参数）
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/__tests__/ConsentPage.test.tsx`
- Create: `frontend/src/__tests__/AdminClientsPage.test.tsx`

**Interfaces:**
- Consumes: 后端 Task 5-7 的 `/oauth2/authorize`、`/api/v1/consent/*`、`/api/v1/admin/clients`。
- Produces: SPA 路由 `/consent`、`/admin/clients`；`consentApi`、`adminClientsApi`；登录页 `next` 回跳。

- [ ] **Step 1: 编写失败测试**

`frontend/src/__tests__/ConsentPage.test.tsx`：

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ConsentPage } from "../pages/ConsentPage";

describe("ConsentPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("同意后跳转到 redirect_url", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            request_id: "r1",
            client: { name: "Demo", logo_url: null, description: "" },
            scopes: ["openid", "profile"],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ redirect_url: "http://localhost:3001/callback?code=abc" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      );
    vi.stubGlobal("fetch", fetchMock);
    const original = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "" },
      writable: true,
      configurable: true,
    });

    render(
      <MemoryRouter initialEntries={["/consent?request_id=r1"]}>
        <ConsentPage />
      </MemoryRouter>
    );
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "同意授权" }));
    await waitFor(() =>
      expect(window.location.href).toBe("http://localhost:3001/callback?code=abc")
    );
    Object.defineProperty(window, "location", { value: original, configurable: true });
  });
});
```

`frontend/src/__tests__/AdminClientsPage.test.tsx`：

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AdminClientsPage } from "../pages/AdminClientsPage";

describe("AdminClientsPage", () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
  });

  it("渲染应用列表", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "1",
            client_id: "cli_demo",
            name: "Demo",
            description: "",
            logo_url: null,
            redirect_uris: ["http://localhost:3001/callback"],
            scopes: ["openid"],
            require_consent_every_time: false,
            is_active: true,
            created_at: "2026-08-12T00:00:00Z",
          },
        ]),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<AdminClientsPage />);
    await waitFor(() => expect(screen.getByText("Demo")).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test`

Expected: FAIL（页面不存在）。

- [ ] **Step 3: 实现类型、API 与页面**

`frontend/src/api/types.ts` 追加：

```ts
export interface ConsentInfo {
  request_id: string;
  client: { name: string; logo_url: string | null; description: string };
  scopes: string[];
}

export interface ClientOut {
  id: string;
  client_id: string;
  name: string;
  description: string;
  logo_url: string | null;
  redirect_uris: string[];
  scopes: string[];
  require_consent_every_time: boolean;
  is_active: boolean;
  created_at: string;
}

export interface ClientCreate {
  name: string;
  description?: string;
  logo_url?: string | null;
  redirect_uris: string[];
  scopes?: string[];
  require_consent_every_time?: boolean;
  public?: boolean;
}

export interface ClientSecretOut {
  client: ClientOut;
  client_secret: string | null;
}
```

`frontend/src/api/client.ts` 追加：

```ts
import type { ClientCreate, ClientOut, ClientSecretOut, ConsentInfo } from "./types";

export const consentApi = {
  info: (requestId: string) => api<ConsentInfo>(`/api/v1/consent/${requestId}`),
  approve: (requestId: string) =>
    api<{ redirect_url: string }>(`/api/v1/consent/${requestId}/approve`, {
      method: "POST",
    }),
  deny: (requestId: string) =>
    api<{ redirect_url: string }>(`/api/v1/consent/${requestId}/deny`, {
      method: "POST",
    }),
};

export const adminClientsApi = {
  list: () => api<ClientOut[]>("/api/v1/admin/clients"),
  create: (data: ClientCreate) =>
    api<ClientSecretOut>("/api/v1/admin/clients", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
```

`frontend/src/pages/ConsentPage.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { consentApi } from "../api/client";
import type { ConsentInfo } from "../api/types";

export function ConsentPage() {
  const [searchParams] = useSearchParams();
  const requestId = searchParams.get("request_id") ?? "";
  const [info, setInfo] = useState<ConsentInfo | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!requestId) return;
    consentApi
      .info(requestId)
      .then(setInfo)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, [requestId]);

  async function decide(approve: boolean) {
    setError("");
    try {
      const result = approve
        ? await consentApi.approve(requestId)
        : await consentApi.deny(requestId);
      window.location.href = result.redirect_url;
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">授权确认</h1>
        {info ? (
          <>
            <p>
              <strong>{info.client.name}</strong> 想获取以下权限：
            </p>
            <ul className="list-disc pl-6">
              {info.scopes.map((scope) => (
                <li key={scope}>{scope}</li>
              ))}
            </ul>
            {error && <p className="text-red-600">{error}</p>}
            <div className="flex gap-2">
              <button
                onClick={() => decide(true)}
                className="flex-1 rounded bg-blue-600 p-2 text-white"
              >
                同意授权
              </button>
              <button
                onClick={() => decide(false)}
                className="flex-1 rounded bg-gray-300 p-2"
              >
                拒绝
              </button>
            </div>
          </>
        ) : (
          <p>{error || "加载中…"}</p>
        )}
      </div>
    </main>
  );
}
```

`frontend/src/pages/AdminClientsPage.tsx`：

```tsx
import { useEffect, useState } from "react";

import { adminClientsApi } from "../api/client";
import type { ClientOut } from "../api/types";

export function AdminClientsPage() {
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [name, setName] = useState("");
  const [redirectUris, setRedirectUris] = useState("");
  const [isPublic, setIsPublic] = useState(true);
  const [secret, setSecret] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    adminClientsApi
      .list()
      .then(setClients)
      .catch((err) => setError(err instanceof Error ? err.message : "加载失败"));
  }, []);

  async function handleCreate(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSecret(null);
    try {
      const result = await adminClientsApi.create({
        name,
        redirect_uris: redirectUris
          .split("\n")
          .map((item) => item.trim())
          .filter(Boolean),
        public: isPublic,
      });
      setClients([result.client, ...clients]);
      setSecret(result.client_secret);
      setName("");
      setRedirectUris("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-8">
      <h1 className="mb-6 text-2xl font-bold">授权网站管理</h1>
      <form onSubmit={handleCreate} className="mb-8 space-y-3 rounded-xl bg-white p-6 shadow">
        <label className="block">
          名称
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          回调地址（每行一个）
          <textarea
            value={redirectUris}
            onChange={(e) => setRedirectUris(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isPublic}
            onChange={(e) => setIsPublic(e.target.checked)}
          />
          公开客户端（无 secret，仅 PKCE）
        </label>
        {secret && (
          <p className="rounded bg-yellow-50 p-2 text-sm">
            请立即保存 client_secret（只显示一次）：<code>{secret}</code>
          </p>
        )}
        {error && <p className="text-red-600">{error}</p>}
        <button type="submit" className="rounded bg-blue-600 p-2 text-white">
          创建应用
        </button>
      </form>
      <ul className="space-y-2">
        {clients.map((client) => (
          <li key={client.id} className="rounded-xl bg-white p-4 shadow">
            <p className="font-semibold">{client.name}</p>
            <p className="text-sm text-gray-500">{client.client_id}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

`frontend/src/pages/LoginPage.tsx` 修改：引入 `useSearchParams`，读取 `next`，登录成功后 `navigate(next)`（默认 `"/"`）。

`frontend/src/App.tsx` 追加路由：

```tsx
import { ConsentPage } from "./pages/ConsentPage";
import { AdminClientsPage } from "./pages/AdminClientsPage";
...
<Route path="/consent" element={<ConsentPage />} />
<Route path="/admin/clients" element={<AdminClientsPage />} />
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd frontend && npm run test && npm run build`

Expected: PASS（4 passed）+ 构建成功。

- [ ] **Step 5: 提交**

```bash
git add frontend
git commit -m "feat: 前端授权确认页与应用管理页"
```

---

### Task 9: 示例授权网站、种子脚本与端到端验证

**Files:**
- Create: `examples/demo-site/app.py`
- Create: `examples/demo-site/requirements.txt`
- Create: `examples/demo-site/Dockerfile`
- Create: `backend/scripts/seed_demo_client.py`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes: 后端全部 OIDC 端点；`demo-site` 客户端（public、redirect `http://localhost:3001/callback`）。
- Produces: 示例网站 `:3001`；`python -m scripts.seed_demo_client` 幂等种子脚本；端到端闭环验证通过。

- [ ] **Step 1: 编写示例网站**

`examples/demo-site/requirements.txt`：

```text
flask==3.1.0
requests==2.32.3
```

`examples/demo-site/app.py`：

```python
import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
from flask import Flask, redirect, render_template_string, request, session, url_for

ISSUER = os.environ.get("PORTAL_ISSUER", "http://localhost:8000")
CLIENT_ID = os.environ.get("PORTAL_CLIENT_ID", "demo-site")
REDIRECT_URI = os.environ.get("DEMO_REDIRECT_URI", "http://localhost:3001/callback")

app = Flask(__name__)
app.secret_key = os.environ.get("DEMO_SECRET_KEY", "demo-secret-key")

AUTHORIZE_URL = f"{ISSUER}/oauth2/authorize"
TOKEN_URL = f"{ISSUER}/oauth2/token"
USERINFO_URL = f"{ISSUER}/oauth2/userinfo"

INDEX_HTML = """
<!doctype html>
<html>
  <body style="font-family: sans-serif; max-width: 640px; margin: 40px auto">
    <h1>示例授权网站</h1>
    {% if user %}
      <p>已通过门户登录：</p>
      <ul>
        <li>邮箱：{{ user.email }}</li>
        <li>昵称：{{ user.nickname }}</li>
        <li>邮箱已验证：{{ user.email_verified }}</li>
      </ul>
      <form method="post" action="{{ url_for('logout') }}">
        <button type="submit">退出登录</button>
      </form>
    {% else %}
      <p><a href="{{ url_for('login') }}">通过门户登录</a></p>
    {% endif %}
  </body>
</html>
"""


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@app.get("/")
def index():
    return render_template_string(INDEX_HTML, user=session.get("user"))


@app.get("/login")
def login():
    verifier, challenge = pkce_pair()
    session["verifier"] = verifier
    session["state"] = secrets.token_urlsafe(24)
    session["nonce"] = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
        "state": session["state"],
        "nonce": session["nonce"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")


@app.get("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return f"授权失败: {error}", 400
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state != session.get("state"):
        return "state 校验失败", 400
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": session.get("verifier"),
        },
        timeout=10,
    )
    if response.status_code != 200:
        return f"换取令牌失败: {response.text}", 400
    token = response.json()
    user_response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=10,
    )
    if user_response.status_code != 200:
        return "获取用户信息失败", 400
    session["user"] = user_response.json()
    return redirect(url_for("index"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
```

`examples/demo-site/Dockerfile`：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 3001
CMD ["python", "app.py"]
```

- [ ] **Step 2: 编写种子脚本**

`backend/scripts/seed_demo_client.py`：

```python
from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.oauth_client import OAuthClient

CLIENT_ID = "demo-site"
REDIRECT_URI = "http://localhost:3001/callback"


def main() -> None:
    with SessionLocal() as db:
        client = db.scalar(
            select(OAuthClient).where(OAuthClient.client_id == CLIENT_ID)
        )
        if client is None:
            client = OAuthClient(
                client_id=CLIENT_ID,
                name="Demo Site",
                description="OIDC 示例授权网站",
                redirect_uris=[REDIRECT_URI],
                scopes=["openid", "profile", "email"],
            )
            db.add(client)
        else:
            client.redirect_uris = [REDIRECT_URI]
            client.is_active = True
        db.commit()
    print(f"示例客户端就绪: client_id={CLIENT_ID}（公开客户端，无 secret）")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 更新 compose 与环境配置**

`docker-compose.yml` 的 `backend` 环境追加：

```yaml
      PENDING_REQUEST_STORE: redis
```

并追加服务：

```yaml
  demo-site:
    build: ./examples/demo-site
    environment:
      PORTAL_ISSUER: http://localhost:8000
      PORTAL_CLIENT_ID: demo-site
    ports:
      - "3001:3001"
    depends_on:
      - backend
```

`.env.example` 追加：

```text
PENDING_REQUEST_STORE=memory
JWT_ISSUER=http://localhost:8000
```

`README.md` 的快速开始追加：

```text
示例授权网站（OIDC 演示，端口 3001）：

docker compose up -d --build demo-site
cd backend && .venv/bin/python -m scripts.seed_demo_client
打开 http://localhost:3001 点击“通过门户登录”
```

- [ ] **Step 4: 端到端验证**

先创建示例客户端（需要 Postgres 已启动；命令需要非沙箱权限时加 `require_escalated`）：

```bash
cd backend
.venv/bin/python -m scripts.seed_demo_client
```

再执行完整闭环（把 EMAIL/PASSWORD 换成已注册且已激活的门户账号）：

```bash
# 1. 登录门户
curl -s -c /tmp/portal.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123"}'

# 2. 从示例网站发起登录，拿到门户 authorize 地址
AUTH_URL=$(curl -s -b /tmp/portal.txt -o /dev/null -w '%{redirect_url}' http://localhost:3001/login)

# 3. 携带门户会话访问 authorize（已有会话 → 跳到 /consent?request_id=...）
CONSENT_URL=$(curl -s -b /tmp/portal.txt -c /tmp/portal.txt -o /dev/null -w '%{redirect_url}' "$AUTH_URL")

# 4. 提取 request_id 并同意授权
REQUEST_ID=${CONSENT_URL##*request_id=}
REDIRECT_URL=$(curl -s -b /tmp/portal.txt -X POST \
  "http://localhost:8000/api/v1/consent/$REQUEST_ID/approve" | python3 -c 'import sys,json;print(json.load(sys.stdin)["redirect_url"])')

# 5. 回到示例网站 callback，验证已登录
curl -s -b /tmp/portal.txt -c /tmp/portal.txt "$REDIRECT_URL" | grep -E "邮箱|昵称"
```

Expected: 第 2 步 Location 是门户 `authorize` 地址；第 3 步是 `/consent?request_id=`；第 4 步返回带 `code` 的示例网站地址；第 5 步页面显示门户账号的邮箱/昵称。再次访问 `http://localhost:3001/login` 应直接返回 `code`（不再询问授权）。

- [ ] **Step 5: 提交**

```bash
git add examples backend docker-compose.yml .env.example README.md
git commit -m "feat: 示例授权网站、种子脚本与端到端验证"
```

---

### Task 10: 测试产物清理与 .gitignore 审计

**Files:**
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 里程碑 1-2 全部实现产物。
- Produces: 仓库内测试/构建产物不被跟踪；`git status` 干净。

- [ ] **Step 1: 审计当前忽略规则**

Run: `git status --short --ignored | grep '^!!' | head -50`

Expected: 至少出现 `backend/.venv/`、`backend/.pytest_cache/`、`backend/app/**/__pycache__/`、`frontend/node_modules/`、`frontend/dist/` 等忽略项；发现未忽略的测试产物时记下路径。

- [ ] **Step 2: 补齐测试产物忽略规则**

确认 `.gitignore` 包含以下全部模式（缺失则补上）：

```text
# 测试与构建产物
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
node_modules/
dist/
coverage/
.vite/
.oxlintcache/
*.log
logs/
*.pem
*.sqlite3
```

注意：`*.pem` 覆盖 JWT 私钥及任何测试密钥；`*.sqlite3` 覆盖本地测试数据库文件。若某项已存在（如根目录已有 `__pycache__/`、`node_modules/`），无需重复。

- [ ] **Step 3: 验证工作区干净并提交**

Run:

```bash
git status --short
git add .gitignore
git commit -m "chore: 忽略测试与构建产物"
```

Expected: `git status --short` 只显示 `.gitignore` 的修改（或全空）；提交成功。

---

## 里程碑 2 完成标准

- 应用可通过管理 API 注册（公开客户端或含 client_secret 的机密客户端），非管理员访问返回 403。
- 从示例网站点“通过门户登录” → 门户已有会话时自动进入授权确认页 → 同意后跳回示例网站并显示用户信息；第二次访问不再询问。
- `authorize / token / userinfo / jwks / discovery` 全部可用；PKCE 校验、授权码一次性、redirect_uri 白名单、scope 校验生效。
- 后端 `pytest` 全绿；前端 `npm run test` 全绿且 `npm run build` 成功；端到端脚本跑通。
- 测试/构建产物全部被 `.gitignore` 覆盖，`git status` 干净。
