import os
import tempfile

os.environ.setdefault(
    "JWT_PRIVATE_KEY_PATH", os.path.join(tempfile.gettempdir(), "portal-test-jwt.pem")
)
os.environ.setdefault(
    "AVATAR_UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "portal-test-avatars")
)
os.environ.setdefault(
    "ENCRYPTION_KEY_PATH",
    os.path.join(tempfile.gettempdir(), "portal-test-encryption.key"),
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  确保模型注册到 Base.metadata
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base


@pytest.fixture(autouse=True)
def _clear_memory_state():
    """内存限流器/挑战存储/待授权存储/统计缓存是进程级单例，测试间共享，
    必须在每个用例前清空，避免配额耗尽或跨测试数据串扰。"""
    from app.services.admin_stats import _CACHE as _stats_cache
    from app.services.pending_requests import _memory_store as _pending_store
    from app.services.rate_limit import _memory_limiter
    from app.services.twofa import _memory_store as _twofa_store

    _memory_limiter._items.clear()
    _pending_store._items.clear()
    _twofa_store._items.clear()
    _stats_cache.clear()
    yield


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
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


class CapturingEmailService:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    def send_verification(self, to: str, code: str) -> None:
        self.messages.append(("verification", to, code))

    def send_password_reset(self, to: str, code: str) -> None:
        self.messages.append(("reset", to, code))

    def send_invite(self, to: str, link: str) -> None:
        self.messages.append(("invite", to, link))

    def send_account_deleted(self, to: str, nickname: str | None) -> None:
        self.messages.append(("account_deleted", to, nickname or ""))

    def send_custom_notification(self, to: str, subject: str, body: str) -> None:
        self.messages.append(("custom_notification", to, f"{subject}\n{body}"))

    def send_invite_batch(
        self, items: list[tuple[str, str]]
    ) -> list[Exception | None]:
        results: list[Exception | None] = []
        for to, link in items:
            try:
                self.send_invite(to, link)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results

    def send_custom_notification_batch(
        self, items: list[tuple[str, str, str]]
    ) -> list[Exception | None]:
        results: list[Exception | None] = []
        for to, subject, body in items:
            try:
                self.send_custom_notification(to, subject, body)
                results.append(None)
            except Exception as exc:
                results.append(exc)
        return results


@pytest.fixture()
def captured_email(monkeypatch):
    service = CapturingEmailService()
    monkeypatch.setattr("app.api.routes.auth.get_email_service", lambda: service)
    monkeypatch.setattr("app.api.routes.users.get_email_service", lambda: service)
    monkeypatch.setattr(
        "app.api.routes.admin_users.get_email_service", lambda: service
    )
    monkeypatch.setattr(
        "app.api.routes.admin_notifications.get_email_service",
        lambda: service,
    )
    return service
