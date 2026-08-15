# 里程碑 4：2FA 与安全加固 Implementation Plan

> **状态：已完成（2026-08-12）** —— 最终实现与行为以仓库代码为准；项目品牌名为 **Li&Pass**（TOTP issuer 也使用该名称），部署形态最终包含内置 `gateway`（nginx）单域名网关。部署/运维见 [docs/deployment.md](../../deployment.md)，OIDC 对接见 [docs/oidc-integration.md](../../oidc-integration.md)。本文件为历史实施计划，不替代当前文档。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现邮箱验证码与 TOTP 两种二次验证（含一次性恢复码、管理员重置），并完成限流、审计日志与安全响应头加固。

**Architecture:** 新增 `recovery_codes`、`audit_logs` 表与 `users.totp_secret_encrypted/totp_enabled_at/email_otp_enabled`；TOTP 密钥用 Fernet 加密存储（恢复码/验证码用带服务端密钥的 HMAC）；2FA 挑战存 Redis（测试用内存单例）；登录改为“密码 → 2FA 挑战 → 验证后建会话”；限流器与审计服务独立成模块；FastAPI 中间件补安全响应头。

**Tech Stack:** 新增 pyotp、qrcode（SVG 输出，不依赖 Pillow）；Fernet 来自已有 cryptography。

## Global Constraints

- Python >=3.11；沿用 SQLite 测试夹具与 `tests/helpers.py`；时间戳一律 timezone-aware。
- TOTP secret 只能加密存储（`totp_secret_encrypted`），绝不落明文；恢复码只存 SHA-256 哈希、一次性使用。
- 2FA 挑战 10 分钟有效、错误上限 5 次；登录失败限流 10 次/15 分钟（按邮箱+IP）；邮箱验证码发送限流 5 次/小时。
- 改密、关闭 2FA 必须先验证当前密码；管理员可重置任意用户 2FA（不能查看密钥）。
- 关键操作写审计日志：登录成功/失败、2FA 变更、2FA 登录、管理员重置 2FA、密码修改/重置、黑名单增删。
- id_token 的 `acr` 依据授权码记录的 `auth_method`：2FA 登录为 2fa，否则 1fa。
- 本里程碑在当前会话内联执行（控制器按 TDD 实现并提交）。

---

### Task 1: 依赖、加密工具、模型与迁移

**Files:**
- Modify: `backend/requirements.txt`（pyotp、qrcode）
- Modify: `backend/app/core/config.py`（加密密钥路径、twofa/rate 配置）
- Create: `backend/app/security/crypto.py`
- Modify: `backend/app/models/user.py`（2FA 字段）
- Create: `backend/app/models/recovery_code.py`
- Create: `backend/app/models/audit_log.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/tests/test_crypto_and_models.py`
- Modify: `.gitignore`（`*.key`）

**Interfaces:**
- Produces: `encrypt_str/decrypt_str`；`User.totp_secret_encrypted/totp_enabled_at/email_otp_enabled`；`RecoveryCode`；`AuditLog`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_crypto_and_models.py`：

```python
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.security.crypto import decrypt_str, encrypt_str


def test_crypto_roundtrip() -> None:
    encrypted = encrypt_str("top-secret")
    assert encrypted != "top-secret"
    assert decrypt_str(encrypted) == "top-secret"


def test_twofa_models(db_session) -> None:
    user = User(
        email="a@example.com",
        password_hash="x",
        nickname="A",
        totp_secret_encrypted=encrypt_str("SECRET"),
        email_otp_enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.totp_enabled_at is not None or user.totp_secret_encrypted is not None

    code = RecoveryCode(user_id=user.id, code_hash="h")
    log = AuditLog(actor_type="user", actor_id=user.id, action="login")
    db_session.add_all([code, log])
    db_session.commit()
    assert code.id is not None
    assert log.id is not None
```

说明：`totp_enabled_at` 由 enable 流程写入；模型测试只断言 secret 字段存在。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_crypto_and_models.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现依赖、配置与工具**

`backend/requirements.txt` 追加：

```text
pyotp==0.0.6
qrcode==8.0
```

`backend/app/core/config.py` 追加：

```python
    encryption_key_path: str = "encryption.key"
    twofa_store: str = "memory"
    rate_limiter: str = "memory"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 900
    otp_send_limit: int = 5
    otp_send_window_seconds: int = 3600
```

`backend/app/security/crypto.py`：

```python
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import get_settings


@lru_cache
def _fernet(path: str) -> Fernet:
    key_path = Path(path)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(Fernet.generate_key())
        key_path.chmod(0o600)
    return Fernet(key_path.read_bytes())


def encrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).encrypt(value.encode()).decode()


def decrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).decrypt(value.encode()).decode()
```

`backend/app/models/user.py` 追加：

```python
    totp_secret_encrypted: Mapped[str | None] = mapped_column(String(500))
    totp_enabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_otp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
```

`backend/app/models/recovery_code.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class RecoveryCode(Base):
    __tablename__ = "recovery_codes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/audit_log.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    actor_type: Mapped[str] = mapped_column(String(20), default="user")
    actor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[str | None] = mapped_column(String(64))
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/__init__.py` 导出 `RecoveryCode`、`AuditLog`。`.gitignore` 追加 `*.key`。

- [ ] **Step 4: 运行测试确认通过，生成迁移并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_crypto_and_models.py -v`

Expected: PASS。安装新依赖（`uv pip install -r requirements.txt`），生成迁移 `alembic revision --autogenerate -m "add 2fa recovery and audit"` 并 `upgrade head`，确认后提交。

---

### Task 2: 2FA 服务（挑战存储、TOTP、恢复码、邮箱码）

**Files:**
- Create: `backend/app/services/twofa.py`
- Create: `backend/tests/test_twofa_service.py`

**Interfaces:**
- Produces: `TwoFaChallenge`；`get_twofa_store() -> TwoFactorChallengeStore`；`create_challenge(store, user_id, methods) -> challenge_id`；`get_challenge(store, challenge_id)`；`delete_challenge`；`generate_recovery_codes(db, user) -> list[str]`；`consume_recovery_code(db, user, code) -> bool`；`verify_totp(user, code) -> bool`；`enable_totp(user, secret, db)`；`build_otpauth_uri(secret, email)`；`qr_data_url(uri) -> str`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_twofa_service.py`：

```python
import pyotp

from app.models.user import User
from app.services.twofa import (
    build_otpauth_uri,
    consume_recovery_code,
    enable_totp,
    generate_recovery_codes,
    qr_data_url,
    verify_totp,
)


def test_recovery_codes_roundtrip(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    codes = generate_recovery_codes(db_session, user)
    assert len(codes) == 10
    assert consume_recovery_code(db_session, user, codes[0]) is True
    assert consume_recovery_code(db_session, user, codes[0]) is False
    assert consume_recovery_code(db_session, user, codes[1]) is True


def test_totp_enable_and_verify(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    secret = pyotp.random_base32()
    enable_totp(user, secret, db_session)
    totp = pyotp.TOTP(secret)
    assert verify_totp(user, totp.now()) is True
    assert verify_totp(user, "000000") is False


def test_otpauth_uri_and_qr(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    uri = build_otpauth_uri("SECRET", user.email)
    assert uri.startswith("otpauth://totp/")
    assert qr_data_url(uri).startswith("data:image/svg+xml;base64,")
```

- [ ] **Step 2: 运行测试确认失败**

Expected: FAIL（模块不存在）。

- [ ] **Step 3: 实现服务**

`backend/app/services/twofa.py`（要点）：

```python
import base64
import io
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
import qrcode.image.svg
import redis

from app.core.config import get_settings
from app.models.recovery_code import RecoveryCode
from app.security.crypto import decrypt_str, encrypt_str
from app.security.tokens import hash_token


@dataclass
class TwoFaChallenge:
    user_id: str
    methods: list[str]
    attempts: int = 0
    expires_at: str = ""


class TwoFactorChallengeStore:
    def create(self, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> str: ...
    def get(self, challenge_id: str) -> TwoFaChallenge | None: ...
    def save(self, challenge_id: str, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> None: ...
    def delete(self, challenge_id: str) -> None: ...


class InMemoryTwoFactorChallengeStore(TwoFactorChallengeStore):
    def __init__(self) -> None:
        self._items: dict[str, tuple[TwoFaChallenge, datetime]] = {}

    def create(self, challenge, ttl_seconds=600):
        challenge_id = secrets.token_urlsafe(24)
        challenge.expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).isoformat()
        self._items[challenge_id] = (challenge, datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds))
        return challenge_id

    def get(self, challenge_id):
        item = self._items.get(challenge_id)
        if item is None:
            return None
        challenge, expires = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(challenge_id, None)
            return None
        return challenge

    def save(self, challenge_id, challenge, ttl_seconds=600):
        self._items[challenge_id] = (challenge, datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds))

    def delete(self, challenge_id):
        self._items.pop(challenge_id, None)


class RedisTwoFactorChallengeStore(TwoFactorChallengeStore):
    def __init__(self, client): self._client = client
    def _key(self, cid): return f"twofa:{cid}"
    def create(self, challenge, ttl_seconds=600):
        cid = secrets.token_urlsafe(24)
        challenge.expires_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat()
        self._client.setex(self._key(cid), ttl_seconds, json.dumps(challenge.__dict__))
        return cid
    def get(self, cid):
        raw = self._client.get(self._key(cid))
        return TwoFaChallenge(**json.loads(raw)) if raw else None
    def save(self, cid, challenge, ttl_seconds=600):
        self._client.setex(self._key(cid), ttl_seconds, json.dumps(challenge.__dict__))
    def delete(self, cid): self._client.delete(self._key(cid))


_memory_store = InMemoryTwoFactorChallengeStore()
_redis_store = None


def get_twofa_store():
    settings = get_settings()
    if settings.twofa_store == "memory":
        return _memory_store
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisTwoFactorChallengeStore(
            redis.Redis.from_url(settings.redis_url, decode_responses=True)
        )
    return _redis_store


def build_otpauth_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Li&Pass")


def qr_data_url(uri: str) -> str:
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buf = io.StringIO()
    img.save(buf)
    encoded = base64.b64encode(buf.getvalue().encode()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def verify_totp(user, code: str) -> bool:
    if not user.totp_secret_encrypted:
        return False
    return pyotp.TOTP(decrypt_str(user.totp_secret_encrypted)).verify(code, valid_window=1)


def enable_totp(user, secret: str, db) -> None:
    user.totp_secret_encrypted = encrypt_str(secret)
    user.totp_enabled_at = datetime.now(timezone.utc)
    db.commit()


def generate_recovery_codes(db, user) -> list[str]:
    codes = [secrets.token_hex(5) for _ in range(10)]
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=hash_token(code)))
    db.commit()
    return codes


def consume_recovery_code(db, user, code: str) -> bool:
    record = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == hash_token(code),
            RecoveryCode.used_at.is_(None),
        )
    )
    if record is None:
        return False
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return True
```

说明：`select` 从 `sqlalchemy` 导入；`enable_totp` 前先 `db.add(user)` 由调用方保证。

- [ ] **Step 4: 运行测试确认通过并提交**

Run: `cd backend && .venv/bin/python -m pytest tests/test_twofa_service.py -v && .venv/bin/python -m pytest tests/ -q`

Expected: 全绿。提交。

---

### Task 3: 用户 2FA 设置 API

**Files:**
- Modify: `backend/app/schemas/auth.py`（2FA schema）
- Create: `backend/app/api/routes/twofa.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_twofa_settings.py`

**Interfaces:**
- Produces: `GET /api/v1/me/2fa/status`、`POST /api/v1/me/2fa/email/enable`、`POST /api/v1/me/2fa/email/disable`、`GET /api/v1/me/2fa/totp/setup`、`POST /api/v1/me/2fa/totp/enable`、`POST /api/v1/me/2fa/totp/disable`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_twofa_settings.py`（要点）：

```python
import pyotp

from tests.helpers import register_and_login


def test_email_2fa_enable_disable(client, captured_email) -> None:
    register_and_login(client, captured_email)
    assert client.post("/api/v1/me/2fa/email/enable").status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
    response = client.post(
        "/api/v1/me/2fa/email/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is False


def test_totp_setup_enable_and_recovery(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": code, "secret": secret},
    )
    assert response.status_code == 200
    recovery = response.json()["recovery_codes"]
    assert len(recovery) == 10
    status = client.get("/api/v1/me/2fa/status").json()
    assert status["totp_enabled"] is True
    assert status["recovery_codes_remaining"] == 10

    response = client.post(
        "/api/v1/me/2fa/totp/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["totp_enabled"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Expected: FAIL（404）。

- [ ] **Step 3: 实现 schema 与路由**

`backend/app/schemas/auth.py` 追加：

```python
class TwoFaTotpEnable(BaseModel):
    code: str = Field(min_length=6, max_length=6)
    secret: str = Field(min_length=16, max_length=128)


class PasswordConfirm(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
```

`backend/app/api/routes/twofa.py`（要点）：

```python
router = APIRouter(prefix="/api/v1/me/2fa", tags=["twofa"])


@router.get("/status")
def twofa_status(user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    remaining = db.scalar(
        select(func.count()).select_from(RecoveryCode).where(
            RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
        )
    )
    return {
        "email_otp_enabled": user.email_otp_enabled,
        "totp_enabled": user.totp_secret_encrypted is not None,
        "recovery_codes_remaining": remaining or 0,
    }


@router.post("/email/enable")
def enable_email_otp(user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    if user.email_verified_at is None:
        raise HTTPException(400, "请先验证邮箱")
    user.email_otp_enabled = True
    audit(db, user, "2fa_email_enable")
    db.commit()
    return {"message": "邮箱二次验证已开启"}


@router.post("/email/disable")
def disable_email_otp(payload: PasswordConfirm, user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    _require_password(payload.current_password, user)
    user.email_otp_enabled = False
    audit(db, user, "2fa_email_disable")
    db.commit()
    return {"message": "邮箱二次验证已关闭"}


@router.get("/totp/setup")
def totp_setup(user=Depends(get_current_user)) -> dict:
    if user.totp_secret_encrypted:
        raise HTTPException(400, "TOTP 已开启")
    secret = pyotp.random_base32()
    uri = build_otpauth_uri(secret, user.email)
    return {"secret": secret, "otpauth_uri": uri, "qr_data_url": qr_data_url(uri)}


@router.post("/totp/enable")
def totp_enable(payload: TwoFaTotpEnable, user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    if not pyotp.TOTP(payload.secret).verify(payload.code, valid_window=1):
        raise HTTPException(400, "验证码无效")
    enable_totp(user, payload.secret, db)
    codes = generate_recovery_codes(db, user)
    audit(db, user, "2fa_totp_enable")
    db.commit()
    return {"message": "TOTP 已开启", "recovery_codes": codes}


@router.post("/totp/disable")
def totp_disable(payload: PasswordConfirm, user=Depends(get_current_user), db=Depends(get_db)) -> dict:
    _require_password(payload.current_password, user)
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    codes = db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id)).all()
    for code in codes:
        db.delete(code)
    audit(db, user, "2fa_totp_disable")
    db.commit()
    return {"message": "TOTP 已关闭"}
```

说明：`_require_password`、`audit` 由 Task 5 提供；本任务先用最小实现（`_require_password` 直接校验密码；`audit` 调用 Task 5 的服务，若尚未实现则本任务内先写空实现并在 Task 5 替换）。为保持顺序，本任务直接实现 `app/services/audit.py` 的 `log_audit`（Task 5 只做接入扩展）。

- [ ] **Step 4: 运行测试确认通过并提交**

---

### Task 4: 登录两步验证

**Files:**
- Modify: `backend/app/api/routes/auth.py`
- Modify: `backend/app/api/routes/oidc.py`（acr 传递）
- Modify: `backend/app/models/authorization_code.py`（`auth_method` 列）
- Modify: `backend/app/services/oidc.py`（`create_authorization_code` 增加 `auth_method`）
- Modify: `backend/app/security/jwt.py`（`create_id_token` 增加 `acr` 参数）
- Create: `backend/tests/test_twofa_login.py`

**Interfaces:**
- Produces: `POST /api/v1/auth/login` 在启用 2FA 时返回 `{requires_2fa: true, challenge_id, methods}`；`POST /api/v1/auth/2fa/send`；`POST /api/v1/auth/2fa/verify`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_twofa_login.py`（要点）：

```python
import pyotp

from tests.helpers import register_and_login


def enable_email_2fa(client, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/me/2fa/email/enable")


def test_email_2fa_login_flow(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_2fa"] is True
    challenge_id = body["challenge_id"]
    assert "email_otp" in body["methods"]
    assert "lipass_session" not in response.cookies

    code = captured_email.messages[-1][2]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": code},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_totp_login_flow(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/me/2fa/totp/enable", json={"code": code, "secret": secret})
    client.post("/api/v1/auth/logout")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    challenge_id = response.json()["challenge_id"]
    assert response.json()["methods"] == ["totp"]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "totp", "code": pyotp.TOTP(secret).now()},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_recovery_code_login(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    enable = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": pyotp.TOTP(secret).now(), "secret": secret},
    ).json()
    recovery = enable["recovery_codes"][0]
    client.post("/api/v1/auth/logout")
    challenge_id = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    ).json()["challenge_id"]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "recovery", "code": recovery},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_2fa_verify_attempts_lock(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    challenge_id = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    ).json()["challenge_id"]
    for _ in range(5):
        client.post(
            "/api/v1/auth/2fa/verify",
            json={"challenge_id": challenge_id, "method": "email_otp", "code": "000000"},
        )
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": "000000"},
    )
    assert response.status_code in (400, 404)
```

- [ ] **Step 2: 运行测试确认失败**

Expected: FAIL（login 未返回 challenge）。

- [ ] **Step 3: 实现**

`backend/app/api/routes/auth.py` 的 `login` 改为：

```python
@router.post("/login")
def login(payload, request, response, db):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        _rate_limit_hit(db, "login", payload.email.lower(), request, response)
        log_audit(db, "user", str(user.id) if user else None, "login_failed", ip=..., user_agent=...)
        raise HTTPException(401, "邮箱或密码错误")
    if user.status != UserStatus.active:
        raise HTTPException(403, "账号已被禁用")
    methods = []
    if user.email_otp_enabled:
        methods.append("email_otp")
    if user.totp_secret_encrypted:
        methods.append("totp")
    if methods:
        challenge_id = create_challenge(get_twofa_store(), str(user.id), methods)
        if user.email_otp_enabled:
            code = create_otp(db, OtpPurpose.two_fa, user.email)
            get_email_service().send_verification(user.email, code)
        return {"requires_2fa": True, "challenge_id": challenge_id, "methods": methods}
    token = _create_session_and_cookie(db, user, request, response, auth_method="password")
    log_audit(db, "user", str(user.id), "login", ip=..., user_agent=...)
    return serialize_user(user)
```

`POST /api/v1/auth/2fa/send`：校验 challenge 存在且 email_otp 在 methods 中，限流后 `create_otp` + 邮件。

`POST /api/v1/auth/2fa/verify`：

```python
store = get_twofa_store()
challenge = store.get(payload.challenge_id)
if challenge is None:
    raise HTTPException(404, "挑战不存在或已过期")
if challenge.attempts >= 5:
    store.delete(payload.challenge_id)
    raise HTTPException(400, "尝试次数过多")
user = db.get(User, uuid.UUID(challenge.user_id))
if user is None or user.status != UserStatus.active:
    raise HTTPException(401, "账号不可用")
ok = False
if payload.method == "totp":
    ok = verify_totp(user, payload.code)
elif payload.method == "email_otp":
    ok = verify_otp(db, OtpPurpose.two_fa, user.email, payload.code)
elif payload.method == "recovery":
    ok = consume_recovery_code(db, user, payload.code)
if not ok:
    challenge.attempts += 1
    store.save(payload.challenge_id, challenge)
    raise HTTPException(400, "验证码无效")
store.delete(payload.challenge_id)
token = _create_session_and_cookie(db, user, request, response, auth_method=payload.method)
log_audit(db, "user", str(user.id), "2fa_login", detail={"method": payload.method}, ...)
return serialize_user(user)
```

`_create_session_and_cookie` 从原 login 逻辑提取（创建 Session、写 Cookie、更新 last_login）。

acr：`AuthorizationCode` 增加 `auth_method`（默认 `"password"`）；`create_authorization_code(..., auth_method="password")`；authorize 自动放行与 approve 用 `get_current_session(request, db).auth_method`；token 端点 `create_id_token(..., acr="urn:lipass:acr:2fa" if record.auth_method in ("email_otp","totp","recovery") else "urn:lipass:acr:1fa")`；`create_id_token` 增加 `acr` 参数并写入 payload。

- [ ] **Step 4: 运行测试确认通过并提交**

---

### Task 5: 限流与审计

**Files:**
- Create: `backend/app/services/rate_limit.py`
- Create: `backend/app/services/audit.py`
- Modify: `backend/app/api/routes/auth.py`、`users.py`、`twofa.py`、`admin_clients.py`、`admin_users.py`（审计/限流接入）
- Create: `backend/app/api/routes/admin_users.py`（重置 2FA、审计列表）
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_rate_limit_and_audit.py`

**Interfaces:**
- Produces: `RateLimiter`（`is_limited/hit/reset`）+ `get_rate_limiter()`；`log_audit(db, actor_type, actor_id, action, target_type=None, target_id=None, ip=None, user_agent=None, detail=None)`；`POST /api/v1/admin/users/{id}/reset-2fa`；`GET /api/v1/admin/audit-logs`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_rate_limit_and_audit.py`（要点）：

```python
def test_login_rate_limit(client, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")
    for _ in range(10):
        client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong"})
    response = client.post("/api/v1/auth/login", json={"email": "a@example.com", "password": "wrong"})
    assert response.status_code == 429


def test_audit_logs_written_and_listed(client, db_session) -> None:
    from app.models.user import User, UserRole
    from app.security.passwords import hash_password

    db_session.add(User(email="admin@example.com", password_hash=hash_password("password123"), nickname="A", role=UserRole.admin))
    db_session.commit()
    client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "password123"})
    response = client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 200
    assert any(item["action"] == "login" for item in response.json())


def test_admin_reset_twofa(client, db_session, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/me/2fa/email/enable")
    # 提升为管理员后重置该用户 2FA
    from app.models.user import User, UserRole
    from sqlalchemy import select

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    user.role = UserRole.admin
    db_session.commit()
    response = client.post(f"/api/v1/admin/users/{user.id}/reset-2fa")
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Expected: FAIL。

- [ ] **Step 3: 实现限流器与审计**

`backend/app/services/rate_limit.py`（内存/Redis 单例，`is_limited(scope, key, limit, window_seconds)` + `hit` + `reset`，Redis 用 `INCR` + `EXPIRE`）。

`backend/app/services/audit.py`：

```python
from app.models.audit_log import AuditLog


def log_audit(
    db,
    actor_type: str,
    actor_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            user_agent=user_agent,
            detail=detail,
        )
    )
    db.commit()
```

接入点：login 成功/失败、2FA 登录、2FA 开关、改密、密码重置、管理员重置 2FA、黑名单增删（admin 与自助 API）。

`backend/app/api/routes/admin_users.py`：

```python
router = APIRouter(prefix="/api/v1/admin", tags=["admin-users"], dependencies=[Depends(get_current_admin)])


@router.post("/users/{user_id:uuid}/reset-2fa")
def reset_twofa(user_id, db=Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(404, "用户不存在")
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    user.email_otp_enabled = False
    codes = db.scalars(select(RecoveryCode).where(RecoveryCode.user_id == user.id)).all()
    for code in codes:
        db.delete(code)
    log_audit(db, "admin", str(user.id), "admin_reset_2fa", target_type="user", target_id=str(user.id))
    db.commit()
    return {"message": "已重置该用户的二次验证"}


@router.get("/audit-logs", response_model=list[dict])
def list_audit_logs(limit: int = Query(100, ge=1, le=500), db=Depends(get_db)) -> list[dict]:
    logs = db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        {
            "id": str(log.id),
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "ip": log.ip,
            "detail": log.detail,
            "created_at": log.created_at,
        }
        for log in logs
    ]
```

说明：`log_audit` 内部 commit 与业务 commit 可能交错；接入时先执行业务变更再调用 `log_audit`（其 commit 会一并提交业务变更）。若需要同一事务，可改为不 commit，由调用方 commit；本计划采用“log_audit 负责 commit”的简单约定。

- [ ] **Step 4: 运行测试确认通过并提交**

---

### Task 6: 安全响应头、管理员重置联动与前端

**Files:**
- Modify: `backend/app/main.py`（安全头中间件）
- Modify: `frontend/src/api/types.ts`、`client.ts`
- Modify: `frontend/src/pages/LoginPage.tsx`（2FA 步骤）
- Modify: `frontend/src/pages/DashboardPage.tsx`（安全设置区）
- Modify: `frontend/src/__tests__/LoginPage.test.tsx`
- Create: `frontend/src/__tests__/DashboardTwofa.test.tsx`

**Interfaces:**
- Produces: 安全响应头；前端 2FA 登录步骤与 2FA 设置 UI。

- [ ] **Step 1: 编写失败测试（前端）**

`frontend/src/__tests__/LoginPage.test.tsx` 追加：登录返回 `requires_2fa` 时渲染验证码输入与“验证”按钮。

`frontend/src/__tests__/DashboardTwofa.test.tsx`：mock `/api/v1/me/2fa/status` 与 `/api/v1/me` 后渲染“安全设置”区。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd frontend && npm run test`

- [ ] **Step 3: 实现安全头中间件**

`backend/app/main.py` 在 `create_app()` 内追加：

```python
    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; connect-src 'self' http://localhost:8000; "
            "img-src 'self' data:; style-src 'self' 'unsafe-inline'"
        )
        return response
```

- [ ] **Step 4: 实现前端**

`frontend/src/api/client.ts` 追加：

```ts
export const twofaApi = {
  status: () => api<{ email_otp_enabled: boolean; totp_enabled: boolean; recovery_codes_remaining: number }>("/api/v1/me/2fa/status"),
  enableEmail: () => api<{ message: string }>("/api/v1/me/2fa/email/enable", { method: "POST" }),
  disableEmail: (current_password: string) => api<{ message: string }>("/api/v1/me/2fa/email/disable", { method: "POST", body: JSON.stringify({ current_password }) }),
  totpSetup: () => api<{ secret: string; otpauth_uri: string; qr_data_url: string }>("/api/v1/me/2fa/totp/setup"),
  totpEnable: (code: string, secret: string) => api<{ message: string; recovery_codes: string[] }>("/api/v1/me/2fa/totp/enable", { method: "POST", body: JSON.stringify({ code, secret }) }),
  totpDisable: (current_password: string) => api<{ message: string }>("/api/v1/me/2fa/totp/disable", { method: "POST", body: JSON.stringify({ current_password }) }),
};

export const auth2faApi = {
  send: (challenge_id: string) => api<{ message: string }>("/api/v1/auth/2fa/send", { method: "POST", body: JSON.stringify({ challenge_id }) }),
  verify: (challenge_id: string, method: string, code: string) => api<UserOut>("/api/v1/auth/2fa/verify", { method: "POST", body: JSON.stringify({ challenge_id, method, code }) }),
};
```

`LoginPage`：`authApi.login` 返回 `requires_2fa` 时进入第二步（显示可用方法、验证码输入、发送验证码按钮），成功后 `window.location.href = next`。

`DashboardPage`：新增“安全设置”区：邮箱 2FA 开关、TOTP 开启流程（展示 `otpauth_uri`/QR、输入验证码、展示恢复码一次）、关闭按钮。

`LoginPage` 的 login 返回类型改为 `UserOut & { requires_2fa?: boolean; challenge_id?: string; methods?: string[] }`。

- [ ] **Step 5: 运行测试与构建并提交**

---

### Task 7: E2E 验证与收尾

**Files:**
- Modify: `docker-compose.yml`（backend 环境 `TWOFA_STORE=redis`、`RATE_LIMITER=redis`）
- Modify: `.env.example`、`README.md`

- [ ] **Step 1: 全量测试**

后端 `pytest` 全绿；前端 `npm test` + `npm run build` 全绿。

- [ ] **Step 2: 端到端验证**

重建容器后验证：

1. 注册/激活/登录 → 开启邮箱 2FA → 退出 → 登录返回 `requires_2fa` → 从后端日志取邮箱验证码 → 2FA verify → 登录成功（`/me` 200）。
2. 开启 TOTP → 退出 → 登录 challenge → 用 `pyotp.TOTP(secret).now()` 生成动态码 → verify 成功；恢复码登录同样可用。
3. 连续 10 次错误密码后第 11 次返回 429。
4. 管理员 `GET /api/v1/admin/audit-logs` 能看到 login / 2fa_login 记录；`POST /api/v1/admin/users/{id}/reset-2fa` 后该用户 2FA 关闭。
5. 所有响应包含 `X-Content-Type-Options: nosniff` 等安全头。

- [ ] **Step 3: README/环境配置更新并提交**

`docker-compose.yml` backend 环境追加 `TWOFA_STORE: redis`、`RATE_LIMITER: redis`；`.env.example` 追加 `ENCRYPTION_KEY_PATH=encryption.key`、`TWOFA_STORE=memory`、`RATE_LIMITER=memory`；README 功能特性补 2FA/恢复码/审计/限流。

提交：

```bash
git add backend frontend docker-compose.yml .env.example README.md docs/superpowers/plans/2026-08-12-milestone-4-2fa-security.md
git commit -m "feat: 里程碑 4 二次验证与安全加固"
```

---

## 里程碑 4 完成标准

- 邮箱验证码与 TOTP 均可用于登录；恢复码一次性可用；连续输错 5 次挑战作废。
- 登录失败限流生效（10 次/15 分钟后 429）；邮箱验证码发送限流生效。
- 关键操作有审计日志，管理员可查询并重置用户 2FA。
- 所有响应带安全头；TOTP 密钥加密存储；`acr` 区分 2FA 登录。
- 后端/前端测试全绿；E2E 通过；工作区干净。
