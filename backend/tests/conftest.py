import os
import tempfile

os.environ.setdefault(
    "JWT_PRIVATE_KEY_PATH", os.path.join(tempfile.gettempdir(), "portal-test-jwt.pem")
)
os.environ.setdefault(
    "AVATAR_UPLOAD_DIR", os.path.join(tempfile.gettempdir(), "portal-test-avatars")
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


@pytest.fixture()
def captured_email(monkeypatch):
    service = CapturingEmailService()
    monkeypatch.setattr("app.api.routes.auth.get_email_service", lambda: service)
    return service
