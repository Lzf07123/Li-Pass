# 里程碑 1：项目骨架与基础账号体系 Implementation Plan

> **状态：已完成（2026-08-12）** —— 最终实现与行为以仓库代码为准；项目品牌名为 **Li&Pass**（Compose 等技术标识仍为 `lipass`），部署形态最终包含内置 `gateway`（nginx）单域名网关。部署/运维见 [docs/deployment.md](../../deployment.md)，OIDC 对接见 [docs/oidc-integration.md](../../oidc-integration.md)。本文件为历史实施计划，不替代当前文档。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建统一登录门户的前后端骨架，并实现邮箱注册、邮箱激活、登录/退出（门户会话 Cookie）与找回密码，使“注册 → 激活 → 登录 → 退出”在本地可完整跑通。

**Architecture:** 单仓库前后端分离：`backend/` 为 FastAPI 认证服务（PostgreSQL + Redis），`frontend/` 为 React SPA（Vite + TypeScript + Tailwind）。仓库内不内置反向代理，前端通过 `VITE_API_BASE_URL` 直连后端，后端配置 CORS 白名单；门户会话使用 HttpOnly Cookie，开发环境 SameSite=Lax。

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy 2.0 / Alembic / Pydantic v2 / Argon2id；React 18 / Vite / TypeScript / Tailwind CSS；PostgreSQL 16 / Redis 7；pytest + TestClient；Vitest + React Testing Library。

## Global Constraints

- Python 版本下限 3.11；后端依赖以 `backend/requirements*.txt` 为准，测试可用 SQLite 内存库（`StaticPool`）运行，无需启动 Docker。
- 仓库内不包含任何反向代理组件；前端通过 `VITE_API_BASE_URL` 直连后端，后端用 CORS 白名单放行前端来源。
- 门户会话 Cookie：`HttpOnly=True`；`Secure` 与 `SameSite` 由环境变量控制（开发默认 `false`/`lax`，生产必须 `true`/`none`）。
- 密码一律 Argon2id 哈希；会话令牌、验证码只存 SHA-256 哈希，绝不存明文。
- `email` 是账号唯一主键（全小写存储）；未验证邮箱允许登录，但 `/me` 返回 `email_verified=false`。
- 邮件服务走抽象层：`EMAIL_BACKEND=console` 时把验证码打印到后端控制台；禁止在业务代码里直接调用 SMTP。
- API 统一前缀 `/api/v1`；健康检查 `/healthz` 返回 `{"status":"ok"}`。
- 所有任务采用 TDD：先写失败测试，再实现，再提交；每个任务一个独立 commit。
- 执行命令默认在仓库根目录运行；后端命令需先激活 `.venv`（`source backend/.venv/bin/activate`）。

---

### Task 1: 仓库与后端骨架

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_health.py`
- Create: `.env.example`
- Create: `docker-compose.yml`

**Interfaces:**
- Consumes: 无（首个任务）。
- Produces: `app.core.config.get_settings() -> Settings`（配置单例）；`app.main.create_app() -> FastAPI`（应用工厂）；`GET /healthz`。

- [ ] **Step 1: 编写失败测试**

```python
# backend/tests/test_health.py
from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz() -> None:
    client = TestClient(create_app())
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_health.py -v`

Expected: FAIL，报 `ModuleNotFoundError: No module named 'app'` 或类似错误。

- [ ] **Step 3: 创建依赖清单、配置、应用工厂与基础设施文件**

`backend/requirements.txt`：

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pydantic-settings==2.7.1
email-validator==2.2.0
sqlalchemy==2.0.36
psycopg[binary]==3.2.3
alembic==1.14.0
argon2-cffi==23.1.0
```

`backend/requirements-dev.txt`：

```text
-r requirements.txt
pytest==8.3.4
httpx==0.28.1
aiosqlite==0.20.0
```

`backend/app/core/config.py`：

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Li&Pass"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5432/portal"
    redis_url: str = "redis://localhost:6379/0"
    session_cookie_name: str = "lipass_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_days: int = 30
    cors_origins: list[str] = ["http://localhost:5173"]
    email_backend: str = "console"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`backend/app/main.py`：

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
```

`backend/app/__init__.py`、`backend/app/core/__init__.py`、`backend/tests/__init__.py` 均为空文件。

`.env.example`：

```text
DATABASE_URL=postgresql+psycopg://portal:portal@localhost:5432/portal
REDIS_URL=redis://localhost:6379/0
SESSION_COOKIE_SECURE=false
SESSION_COOKIE_SAMESITE=lax
CORS_ORIGINS=["http://localhost:5173"]
EMAIL_BACKEND=console
```

`docker-compose.yml`（本任务只放基础设施，backend/frontend 服务在 Task 8 加入）：

```yaml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: portal
      POSTGRES_PASSWORD: portal
      POSTGRES_DB: portal
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U portal"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

volumes:
  postgres-data:
  redis-data:
```

- [ ] **Step 4: 创建虚拟环境并安装依赖**

Run:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_health.py -v`

Expected: PASS（1 passed）。

- [ ] **Step 6: 提交**

```bash
git add .env.example docker-compose.yml backend
git commit -m "feat: 搭建后端骨架与基础设施配置"
```

---

### Task 2: 数据库核心、用户/会话/验证码模型与迁移

**Files:**
- Create: `backend/app/core/db.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/session.py`
- Create: `backend/app/models/otp.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: `app.core.config.get_settings()`（Task 1）。
- Produces: `app.core.db.get_db() -> Generator[Session]`；模型 `User`、`Session`、`Otp`（含枚举 `UserRole`、`UserStatus`、`OtpPurpose`）；测试夹具 `client`、`db_session`、`engine`。

- [ ] **Step 1: 编写失败测试（夹具 + 模型冒烟测试）**

`backend/tests/conftest.py`：

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  确保模型注册到 Base.metadata
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture()
def engine():
    return create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


@pytest.fixture()
def db_session(engine):
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(engine):
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    app = create_app()

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


class CapturingEmailService:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send_verification(self, to: str, code: str) -> None:
        self.messages.append(("verification", to, code))

    def send_password_reset(self, to: str, code: str) -> None:
        self.messages.append(("reset", to, code))


@pytest.fixture()
def captured_email(monkeypatch):
    service = CapturingEmailService()
    monkeypatch.setattr("app.api.routes.auth.get_email_service", lambda: service)
    return service
```

`backend/tests/test_models.py`：

```python
from app.models.otp import Otp, OtpPurpose
from app.models.session import Session
from app.models.user import User, UserRole, UserStatus


def test_create_user_session_otp(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="Alice")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.user
    assert user.status == UserStatus.active

    session = Session(user_id=user.id, token_hash="abc", expires_at=user.created_at)
    otp = Otp(purpose=OtpPurpose.register, target=user.email, code_hash="def", expires_at=user.created_at)
    db_session.add_all([session, otp])
    db_session.commit()

    assert session.id is not None
    assert otp.id is not None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`

Expected: FAIL，报模块缺失错误。

- [ ] **Step 3: 创建数据库核心与模型**

`backend/app/core/db.py`：

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`backend/app/models/base.py`：

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

`backend/app/models/user.py`：

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class UserStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str] = mapped_column(String(255))
    nickname: Mapped[str] = mapped_column(String(80), default="")
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.active)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(String(64))
```

`backend/app/models/session.py`：

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    auth_method: Mapped[str] = mapped_column(String(20), default="password")
    device_name: Mapped[str] = mapped_column(String(120), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/otp.py`：

```python
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class OtpPurpose(str, enum.Enum):
    register = "register"
    reset_password = "reset_password"
    bind_phone = "bind_phone"
    two_fa = "2fa"


class Otp(Base):
    __tablename__ = "otps"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    purpose: Mapped[OtpPurpose] = mapped_column(Enum(OtpPurpose), index=True)
    target: Mapped[str] = mapped_column(String(320), index=True)
    code_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

`backend/app/models/__init__.py`：

```python
from app.models.base import Base
from app.models.otp import Otp, OtpPurpose
from app.models.session import Session
from app.models.user import User, UserRole, UserStatus

__all__ = ["Base", "Otp", "OtpPurpose", "Session", "User", "UserRole", "UserStatus"]
```

- [ ] **Step 4: 初始化 Alembic 并生成迁移**

Run（在 `backend/` 目录，激活虚拟环境）：

```bash
alembic init alembic
```

编辑 `backend/alembic/env.py`：把 `sqlalchemy.url` 配置改为读取应用配置，并让 `target_metadata` 指向 `app.models.Base.metadata`。关键修改：

```python
from app.core.config import get_settings
from app.models.base import Base

config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata
```

然后在 `backend/app/__init__.py` 保持为空即可，`env.py` 顶部补 `from app import models  # noqa` 保证模型注册。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`

Expected: PASS（1 passed）。

- [ ] **Step 6: 生成初始迁移并提交**

Run:

```bash
cd backend
alembic revision --autogenerate -m "create users sessions otps"
```

确认生成的迁移包含 `users`、`sessions`、`otps` 三张表后提交：

```bash
git add backend
git commit -m "feat: 添加用户/会话/验证码模型与数据库迁移"
```

---

### Task 3: 安全工具、邮件抽象与验证码服务

**Files:**
- Create: `backend/app/security/__init__.py`
- Create: `backend/app/security/passwords.py`
- Create: `backend/app/security/tokens.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/email.py`
- Create: `backend/app/services/otps.py`
- Create: `backend/tests/test_security.py`
- Create: `backend/tests/test_otps.py`

**Interfaces:**
- Consumes: `Settings`（Task 1）、`Otp`/`OtpPurpose`（Task 2）、`Session`（测试用）。
- Produces: `hash_password(password) -> str`；`verify_password(password, password_hash) -> bool`；`generate_token() -> str`；`hash_token(token) -> str`；`generate_otp_code() -> str`；`hash_otp_code(code) -> str`；`get_email_service() -> EmailService`（含 `send_verification(to, code)`、`send_password_reset(to, code)`）；`create_otp(db, purpose, target, ttl_minutes=10) -> str`；`verify_otp(db, purpose, target, code) -> bool`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_security.py`：

```python
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_otp_code, generate_token, hash_otp_code, hash_token


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("password123")
    assert password_hash != "password123"
    assert verify_password("password123", password_hash) is True
    assert verify_password("wrong", password_hash) is False


def test_token_and_otp_hashing() -> None:
    token = generate_token()
    assert len(token) >= 32
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token

    code = generate_otp_code()
    assert len(code) == 6 and code.isdigit()
    assert hash_otp_code(code) == hash_otp_code(code)
```

`backend/tests/test_otps.py`：

```python
from datetime import datetime, timedelta, timezone

from app.models.otp import Otp, OtpPurpose
from app.security.tokens import hash_otp_code
from app.services.otps import create_otp, verify_otp


def test_create_and_verify_otp(db_session) -> None:
    code = create_otp(db_session, OtpPurpose.register, "A@Example.com")
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is True
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is False  # 一次性


def test_otp_wrong_code_increments_attempts(db_session) -> None:
    code = create_otp(db_session, OtpPurpose.register, "a@example.com")
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", "000000") is False
    otp = db_session.query(Otp).one()
    assert otp.attempts == 1
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is True


def test_otp_expired(db_session) -> None:
    from app.models.base import Base

    otp = Otp(
        purpose=OtpPurpose.register,
        target="a@example.com",
        code_hash=hash_otp_code("123456"),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(otp)
    db_session.commit()
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", "123456") is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_security.py tests/test_otps.py -v`

Expected: FAIL，模块缺失。

- [ ] **Step 3: 实现安全工具与验证码服务**

`backend/app/security/passwords.py`：

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
```

`backend/app/security/tokens.py`：

```python
import hashlib
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()
```

`backend/app/services/email.py`：

```python
from abc import ABC, abstractmethod

from app.core.config import get_settings


class EmailService(ABC):
    @abstractmethod
    def send_verification(self, to: str, code: str) -> None: ...

    @abstractmethod
    def send_password_reset(self, to: str, code: str) -> None: ...


class ConsoleEmailService(EmailService):
    def _send(self, subject: str, to: str, code: str) -> None:
        print(f"[email:{get_settings().email_backend}] {subject} -> {to}: code={code}")

    def send_verification(self, to: str, code: str) -> None:
        self._send("verify your email", to, code)

    def send_password_reset(self, to: str, code: str) -> None:
        self._send("reset your password", to, code)


def get_email_service() -> EmailService:
    if get_settings().email_backend == "console":
        return ConsoleEmailService()
    raise ValueError(f"Unsupported email backend: {get_settings().email_backend}")
```

`backend/app/services/otps.py`：

```python
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.otp import Otp, OtpPurpose
from app.security.tokens import generate_otp_code, hash_otp_code

MAX_ATTEMPTS = 5
OTP_TTL_MINUTES = 10


def create_otp(
    db: Session, purpose: OtpPurpose, target: str, ttl_minutes: int = OTP_TTL_MINUTES
) -> str:
    code = generate_otp_code()
    db.add(
        Otp(
            purpose=purpose,
            target=target.lower(),
            code_hash=hash_otp_code(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return code


def verify_otp(db: Session, purpose: OtpPurpose, target: str, code: str) -> bool:
    otp = db.scalar(
        select(Otp)
        .where(Otp.purpose == purpose, Otp.target == target.lower(), Otp.consumed_at.is_(None))
        .order_by(Otp.created_at.desc())
    )
    if otp is None:
        return False
    if otp.attempts >= MAX_ATTEMPTS or otp.expires_at < datetime.now(timezone.utc):
        return False
    if secrets.compare_digest(hash_otp_code(code), otp.code_hash):
        otp.consumed_at = datetime.now(timezone.utc)
        otp.attempts += 1
        db.commit()
        return True
    otp.attempts += 1
    db.commit()
    return False
```

`backend/app/security/__init__.py`、`backend/app/services/__init__.py` 为空文件。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_security.py tests/test_otps.py -v`

Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 添加密码哈希、令牌/验证码工具、邮件与 OTP 服务"
```

---

### Task 4: 注册、邮箱激活与当前用户接口

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/auth.py`
- Create: `backend/app/api/routes/users.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_register.py`

**Interfaces:**
- Consumes: Task 1-3 的全部接口；`User`/`OtpPurpose` 模型。
- Produces: `POST /api/v1/auth/register`、`POST /api/v1/auth/email/verify`、`GET /api/v1/me`；`app.api.deps.get_current_user(request, db) -> User`；`app.schemas.auth.serialize_user(user) -> dict`。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_auth_register.py`：

```python
from sqlalchemy import select

from app.models.user import User


def test_register_verify_updates_user(client, db_session, captured_email) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "A@Example.com", "password": "password123", "nickname": "Alice"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@example.com"
    assert body["email_verified"] is False

    code = captured_email.messages[0][2]
    response = client.post(
        "/api/v1/auth/email/verify",
        json={"email": "a@example.com", "code": code},
    )
    assert response.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert user is not None
    assert user.email_verified_at is not None


def test_register_duplicate_email(client, captured_email) -> None:
    payload = {"email": "a@example.com", "password": "password123", "nickname": "Alice"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_me_requires_session(client) -> None:
    assert client.get("/api/v1/me").status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_register.py -v`

Expected: FAIL（404 或导入错误）。

- [ ] **Step 3: 实现校验模型、依赖与路由**

`backend/app/schemas/auth.py`：

```python
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=80)


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    device_name: str = ""


class PasswordResetRequest(BaseModel):
    email: EmailStr


class ConfirmPasswordResetRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    nickname: str
    email_verified: bool
    role: str
    status: str


def serialize_user(user) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "email_verified": user.email_verified_at is not None,
        "role": user.role.value,
        "status": user.status.value,
    }
```

`backend/app/api/deps.py`：

```python
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.session import Session as SessionModel
from app.models.user import User, UserStatus
from app.security.tokens import hash_token


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
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
        or session.expires_at < now
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User unavailable")

    session.last_used_at = now
    db.commit()
    return user
```

`backend/app/api/routes/auth.py`：

```python
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.otp import OtpPurpose
from app.models.user import User
from app.schemas.auth import (
    EmailVerifyRequest,
    RegisterRequest,
    UserOut,
    serialize_user,
)
from app.security.passwords import hash_password
from app.services.email import get_email_service
from app.services.otps import create_otp, verify_otp

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.commit()

    code = create_otp(db, OtpPurpose.register, email)
    get_email_service().send_verification(email, code)
    return serialize_user(user)


@router.post("/email/verify")
def verify_email(payload: EmailVerifyRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    if not verify_otp(db, OtpPurpose.register, email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "邮箱已验证"}
```

`backend/app/api/routes/users.py`：

```python
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.auth import UserOut, serialize_user

router = APIRouter(prefix="/api/v1", tags=["users"])


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)
```

`backend/app/main.py` 在 `create_app()` 内注册路由（`app = create_app()` 之前追加 import 与 include）：

```python
from app.api.routes import auth as auth_routes
from app.api.routes import users as user_routes


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    # ...原有 CORS 中间件与 /healthz 保持不变...
    app.include_router(auth_routes.router)
    app.include_router(user_routes.router)
    return app
```

`backend/app/schemas/__init__.py`、`backend/app/api/__init__.py`、`backend/app/api/routes/__init__.py` 为空文件。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_register.py -v`

Expected: PASS（3 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 实现注册、邮箱激活与当前用户接口"
```

---

### Task 5: 登录与退出

**Files:**
- Create: `backend/tests/test_auth_login.py`

**Interfaces:**
- Consumes: Task 4 的 `POST /api/v1/auth/login`、`POST /api/v1/auth/logout`、`GET /api/v1/me`。
- Produces: 门户会话 Cookie `lipass_session`；登录/退出行为契约（见测试）。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_auth_login.py`：

```python
from sqlalchemy import select

from app.models.user import User, UserStatus


def register_and_verify(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})


def test_login_logout_flow(client, captured_email) -> None:
    register_and_verify(client, captured_email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies

    assert client.get("/api/v1/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/me").status_code == 401


def test_login_wrong_password(client, captured_email) -> None:
    register_and_verify(client, captured_email)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_disabled_user_cannot_login(client, db_session, captured_email) -> None:
    register_and_verify(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    user.status = UserStatus.disabled
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 403


def test_unverified_user_can_login_but_flagged(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["email_verified"] is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_login.py -v`

Expected: FAIL（`lipass_session` 未设置或断言失败）。

- [ ] **Step 3: 实现登录与退出路由**

将以下代码追加到 `backend/app/api/routes/auth.py`，并在文件顶部补充相应 import：

```python
# 在文件顶部补充：
# from datetime import timedelta
# from fastapi import Response
# from app.models.session import Session as SessionModel
# from app.models.user import UserStatus
# from app.schemas.auth import LoginRequest
# from app.security.passwords import verify_password
# from app.security.tokens import generate_token, hash_token


@router.post("/login", response_model=UserOut)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if user.status != UserStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")

    now = datetime.now(timezone.utc)
    token = generate_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        device_name=payload.device_name,
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_used_at=now,
    )
    db.add(session)
    user.last_login_at = now
    user.last_login_ip = request.client.host if request.client else None
    db.commit()

    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_days * 86400,
    )
    return serialize_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(
            select(SessionModel).where(SessionModel.token_hash == hash_token(token))
        )
        if session is not None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie(settings.session_cookie_name)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_login.py -v`

Expected: PASS（4 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 实现登录/退出与门户会话 Cookie"
```

---

### Task 6: 找回密码

**Files:**
- Create: `backend/tests/test_auth_password_reset.py`

**Interfaces:**
- Consumes: Task 4 的 `POST /api/v1/auth/password/reset`、`POST /api/v1/auth/password/reset/confirm`、`POST /api/v1/auth/login`。
- Produces: 找回密码行为契约（见测试）。

- [ ] **Step 1: 编写失败测试**

`backend/tests/test_auth_password_reset.py`：

```python
def test_password_reset_flow(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )

    response = client.post(
        "/api/v1/auth/password/reset", json={"email": "a@example.com"}
    )
    assert response.status_code == 202
    code = captured_email.messages[-1][2]

    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"email": "a@example.com", "code": code, "new_password": "newpassword456"},
    )
    assert response.status_code == 200

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "newpassword456"},
    )
    assert response.status_code == 200


def test_password_reset_bad_code(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    response = client.post(
        "/api/v1/auth/password/reset/confirm",
        json={"email": "a@example.com", "code": "000000", "new_password": "newpassword456"},
    )
    assert response.status_code == 400
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_password_reset.py -v`

Expected: FAIL。

- [ ] **Step 3: 实现找回密码路由**

将以下代码追加到 `backend/app/api/routes/auth.py`，并在文件顶部补充相应 import：

```python
# 在文件顶部补充：
# from app.schemas.auth import ConfirmPasswordResetRequest, PasswordResetRequest


@router.post("/password/reset", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest, db: Session = Depends(get_db)
) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        code = create_otp(db, OtpPurpose.reset_password, email)
        get_email_service().send_password_reset(email, code)
    return {"message": "如果该邮箱已注册，重置验证码已发送"}


@router.post("/password/reset/confirm")
def confirm_password_reset(
    payload: ConfirmPasswordResetRequest, db: Session = Depends(get_db)
) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_otp(db, OtpPurpose.reset_password, email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "密码已重置"}
```

注意：未注册邮箱也返回 202 与相同提示，避免枚举邮箱。

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && .venv/bin/python -m pytest tests/test_auth_password_reset.py -v`

Expected: PASS（2 passed）。

- [ ] **Step 5: 提交**

```bash
git add backend
git commit -m "feat: 实现找回密码流程"
```

---

### Task 7: React 前端骨架与认证页面

**Files:**
- Create: `frontend/`（Vite react-ts 模板）
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/index.css`
- Create: `frontend/src/api/types.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/pages/LoginPage.tsx`
- Create: `frontend/src/pages/RegisterPage.tsx`
- Create: `frontend/src/pages/ForgotPasswordPage.tsx`
- Create: `frontend/src/pages/VerifyEmailPage.tsx`
- Create: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/test/setup.ts`
- Create: `frontend/src/__tests__/RegisterPage.test.tsx`
- Create: `frontend/src/__tests__/LoginPage.test.tsx`

**Interfaces:**
- Consumes: 后端 Task 4-6 的 `/api/v1/auth/*` 与 `/api/v1/me`。
- Produces: SPA 路由 `/login`、`/register`、`/forgot-password`、`/verify-email`、`/`（Dashboard）；API 客户端 `authApi`（`register/verifyEmail/login/logout/me/requestPasswordReset/confirmPasswordReset`）；前端测试通过。

- [ ] **Step 1: 脚手架与依赖**

Run:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install react-router-dom tailwindcss @tailwindcss/vite
npm install -D vitest jsdom @testing-library/react @testing-library/jest-dom
```

`frontend/vite.config.ts`：

```ts
/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
```

`frontend/src/index.css`：

```css
@import "tailwindcss";
```

`frontend/src/test/setup.ts`：

```ts
import "@testing-library/jest-dom/vitest";
```

`frontend/package.json` 的 `scripts` 增加：`"test": "vitest run"`。

- [ ] **Step 2: 编写失败测试**

`frontend/src/__tests__/RegisterPage.test.tsx`：

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { RegisterPage } from "../pages/RegisterPage";

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("提交注册请求并跳转到验证页", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "1",
          email: "a@example.com",
          nickname: "Alice",
          email_verified: false,
          role: "user",
          status: "active",
        }),
        { status: 201, headers: { "Content-Type": "application/json" } }
      )
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <RegisterPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("昵称"), { target: { value: "Alice" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "password123" } });
    fireEvent.click(screen.getByRole("button", { name: "注册" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/api/v1/auth/register");
    expect(init.method).toBe("POST");
    expect(JSON.parse(String(init.body))).toEqual({
      email: "a@example.com",
      nickname: "Alice",
      password: "password123",
    });
  });
});
```

`frontend/src/__tests__/LoginPage.test.tsx`：

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../pages/LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("登录失败时展示错误信息", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "邮箱或密码错误" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      })
    );
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByLabelText("邮箱"), { target: { value: "a@example.com" } });
    fireEvent.change(screen.getByLabelText("密码"), { target: { value: "wrongpass" } });
    fireEvent.click(screen.getByRole("button", { name: "登录" }));

    await waitFor(() => expect(screen.getByText("邮箱或密码错误")).toBeInTheDocument());
  });
});
```

- [ ] **Step 3: 运行测试确认失败**

Run: `cd frontend && npm run test`

Expected: FAIL（页面/API 客户端不存在）。

- [ ] **Step 4: 实现 API 客户端与页面**

`frontend/src/api/types.ts`：

```ts
export interface UserOut {
  id: string;
  email: string;
  nickname: string;
  email_verified: boolean;
  role: string;
  status: string;
}
```

`frontend/src/api/client.ts`：

```ts
import type { UserOut } from "./types";

const BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 204) {
    return undefined as T;
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `请求失败：${response.status}`);
  }
  return response.json() as Promise<T>;
}

export const authApi = {
  register: (data: { email: string; password: string; nickname: string }) =>
    api<UserOut>("/api/v1/auth/register", { method: "POST", body: JSON.stringify(data) }),
  verifyEmail: (data: { email: string; code: string }) =>
    api<{ message: string }>("/api/v1/auth/email/verify", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  login: (data: { email: string; password: string }) =>
    api<UserOut>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(data) }),
  logout: () => api<void>("/api/v1/auth/logout", { method: "POST" }),
  me: () => api<UserOut>("/api/v1/me"),
  requestPasswordReset: (data: { email: string }) =>
    api<{ message: string }>("/api/v1/auth/password/reset", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  confirmPasswordReset: (data: { email: string; code: string; new_password: string }) =>
    api<{ message: string }>("/api/v1/auth/password/reset/confirm", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
```

`frontend/src/pages/RegisterPage.tsx`：

```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";

export function RegisterPage() {
  const [email, setEmail] = useState("");
  const [nickname, setNickname] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await authApi.register({ email, nickname, password });
      navigate(`/verify-email?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">注册 Li&Pass 账号</h1>
        <label className="block">
          邮箱
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          昵称
          <input
            value={nickname}
            onChange={(e) => setNickname(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            minLength={8}
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          注册
        </button>
        <p>
          已有账号？<Link to="/login" className="text-blue-600">去登录</Link>
        </p>
      </form>
    </main>
  );
}
```

`frontend/src/pages/LoginPage.tsx`：

```tsx
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "../api/client";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await authApi.login({ email, password });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">登录 Li&Pass</h1>
        <label className="block">
          邮箱
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        <label className="block">
          密码
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          登录
        </button>
        <p>
          <Link to="/forgot-password" className="text-blue-600">忘记密码？</Link>
          <span className="mx-2">|</span>
          <Link to="/register" className="text-blue-600">注册新账号</Link>
        </p>
      </form>
    </main>
  );
}
```

`frontend/src/pages/ForgotPasswordPage.tsx`：

```tsx
import { useState } from "react";
import { Link } from "react-router-dom";

import { authApi } from "../api/client";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.requestPasswordReset({ email });
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">找回密码</h1>
        <label className="block">
          邮箱
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        {message && <p className="text-green-600">{message}</p>}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          发送重置验证码
        </button>
        <p>
          <Link to="/login" className="text-blue-600">返回登录</Link>
        </p>
      </form>
    </main>
  );
}
```

`frontend/src/pages/VerifyEmailPage.tsx`：

```tsx
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { authApi } from "../api/client";

export function VerifyEmailPage() {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email") ?? "";
  const [code, setCode] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const result = await authApi.verifyEmail({ email, code });
      setMessage(result.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "验证失败");
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-gray-50">
      <form onSubmit={handleSubmit} className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">验证邮箱</h1>
        <p className="text-gray-600">验证码已发送到 {email || "你的邮箱"}</p>
        <label className="block">
          验证码
          <input
            value={code}
            onChange={(e) => setCode(e.target.value)}
            className="mt-1 w-full rounded border p-2"
            maxLength={6}
            required
          />
        </label>
        {error && <p className="text-red-600">{error}</p>}
        {message && (
          <p className="text-green-600">
            {message}，<Link to="/login" className="text-blue-600">去登录</Link>
          </p>
        )}
        <button type="submit" className="w-full rounded bg-blue-600 p-2 text-white">
          验证
        </button>
      </form>
    </main>
  );
}
```

`frontend/src/pages/DashboardPage.tsx`：

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { authApi } from "../api/client";
import type { UserOut } from "../api/types";

export function DashboardPage() {
  const [user, setUser] = useState<UserOut | null>(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    authApi
      .me()
      .then(setUser)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "未登录");
        navigate("/login");
      });
  }, [navigate]);

  async function handleLogout() {
    await authApi.logout();
    navigate("/login");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-gray-50">
      <div className="w-96 space-y-4 rounded-xl bg-white p-8 shadow">
        <h1 className="text-2xl font-bold">用户中心</h1>
        {user ? (
          <>
            <p>邮箱：{user.email}</p>
            <p>昵称：{user.nickname}</p>
            <p>邮箱已验证：{user.email_verified ? "是" : "否"}</p>
            <button onClick={handleLogout} className="w-full rounded bg-red-600 p-2 text-white">
              退出登录
            </button>
          </>
        ) : (
          <p>{error || "加载中…"}</p>
        )}
      </div>
    </main>
  );
}
```

`frontend/src/App.tsx`：

```tsx
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { VerifyEmailPage } from "./pages/VerifyEmailPage";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/verify-email" element={<VerifyEmailPage />} />
        <Route path="/" element={<DashboardPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

删除 Vite 模板自带的 `frontend/src/App.css` 引用（`App.tsx` 不再 import 它），保留 `main.tsx` 的 `import "./index.css"`。

- [ ] **Step 5: 运行测试确认通过**

Run: `cd frontend && npm run test`

Expected: PASS（2 passed）。

- [ ] **Step 6: 提交**

```bash
git add frontend
git commit -m "feat: 添加 React 前端骨架与认证页面"
```

---

### Task 8: Docker Compose 全栈与端到端验证

**Files:**
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Modify: `docker-compose.yml`（加入 backend、frontend 服务）
- Modify: `README.md`（如需修正启动命令）

**Interfaces:**
- Consumes: Task 1-7 全部产物。
- Produces: `docker compose up --build` 可启动 frontend + backend + postgres + redis；端到端 curl 验证通过。

- [ ] **Step 1: 编写 Dockerfile**

`backend/Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY alembic.ini .
COPY alembic ./alembic

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

`frontend/Dockerfile`：

```dockerfile
FROM node:20-alpine AS build
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY --from=build /app/dist ./dist
EXPOSE 5173
CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173"]
```

- [ ] **Step 2: 更新 docker-compose.yml**

在 `docker-compose.yml` 中追加服务（保留 postgres、redis 原定义）：

```yaml
  backend:
    build: ./backend
    environment:
      DATABASE_URL: postgresql+psycopg://portal:portal@postgres:5432/portal
      REDIS_URL: redis://redis:6379/0
      CORS_ORIGINS: '["http://localhost:5173"]'
      SESSION_COOKIE_SECURE: "false"
      SESSION_COOKIE_SAMESITE: lax
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      args:
        VITE_API_BASE_URL: http://localhost:8000
    ports:
      - "5173:5173"
    depends_on:
      - backend
```

- [ ] **Step 3: 启动全栈**

Run: `docker compose up -d --build`

Expected: 四个服务均为 running 或 healthy。

- [ ] **Step 4: 端到端验证完整闭环**

Run:

```bash
curl -s http://localhost:8000/healthz
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123","nickname":"Demo"}'
```

Expected: `/healthz` 返回 `{"status":"ok"}`；注册返回 201。再从后端容器日志中找到验证码：

```bash
docker compose logs backend | grep "code="
```

用日志中的验证码执行激活，然后登录并访问 `/api/v1/me`，最后退出：

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/email/verify \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","code":"<日志中的验证码>"}'

curl -s -c /tmp/portal-cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"password123"}'

curl -s -b /tmp/portal-cookies.txt http://localhost:8000/api/v1/me
curl -s -b /tmp/portal-cookies.txt -X POST http://localhost:8000/api/v1/auth/logout
```

Expected: 激活 200 → 登录 200 且写入 cookie → `/me` 200 → 登出 204。

- [ ] **Step 5: 修正 README 启动说明（如与实测不符）**

检查 [README.md](../../README.md) 的“快速开始”，确保 `docker compose up -d postgres redis` 与手动启动步骤和实测一致；如 compose 已可一键起全套，可在 README 补充：

```text
一键启动全栈（含前端、后端与基础设施）：

docker compose up -d --build
```

- [ ] **Step 6: 提交**

```bash
git add backend/Dockerfile frontend/Dockerfile docker-compose.yml README.md
git commit -m "feat: 完善 Docker Compose 全栈与端到端验证"
```

---

## 里程碑 1 完成标准

- 新用户可通过 API 或前端页面注册，控制台收到邮箱激活码，激活后 `email_verified=true`。
- 用户可登录（获得 HttpOnly 门户会话 Cookie）、查看 `/me`、退出后 `/me` 返回 401。
- 用户可通过邮箱验证码重置密码并用新密码登录。
- `cd backend && pytest` 全绿；`cd frontend && npm run test` 全绿。
- `docker compose up -d --build` 后，curl 端到端闭环全部通过。
