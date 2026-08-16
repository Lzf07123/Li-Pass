import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  确保模型注册到 Base.metadata
from app.core.db import get_db
from app.main import create_app
from app.models.base import Base
from tests.test_config_production import _settings


@pytest.fixture()
def production_client(monkeypatch):
    """使用合法生产配置构建的应用，DB 依赖替换为内存 SQLite。"""
    monkeypatch.setattr(
        "app.main.get_settings",
        lambda: _settings(
            monkeypatch, ALLOWED_HOSTS='["portal.example.com","testserver"]'
        ),
    )
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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


def test_security_headers(client) -> None:
    response = client.get("/healthz")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert "form-action 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert response.headers["accept-ch"] == (
        "Sec-CH-UA-Model, Sec-CH-UA-Platform-Version"
    )
    assert response.headers["cache-control"] == "no-store"


def test_hsts_header_only_in_production(
    client, production_client
) -> None:
    # 开发/测试环境（HTTPS 未启用）不签发 HSTS，避免 HTTP 直连误发。
    assert "strict-transport-security" not in client.get("/healthz").headers

    response = production_client.get("/healthz")
    assert (
        response.headers["strict-transport-security"]
        == "max-age=63072000; includeSubDomains"
    )


def test_cors_allow_methods_are_explicit(client) -> None:
    """带凭据的 CORS 必须使用显式头白名单，而不是通配反射任意请求头。"""
    response = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-credentials"] == "true"
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:5173"
    )
    methods = response.headers["access-control-allow-methods"]
    assert "POST" in methods
    assert "*" not in methods

    # 通配反射模式下任意请求头都会被镜像放行；显式白名单必须拒绝未知头。
    rejected = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "X-Random-Header",
        },
    )
    assert rejected.status_code == 400


def test_production_csp_has_no_unsafe_inline(production_client) -> None:
    csp = production_client.get("/healthz").headers["content-security-policy"]
    assert "style-src 'self'" in csp
    assert "unsafe-inline" not in csp


def test_development_csp_keeps_unsafe_inline_for_docs(client) -> None:
    csp = client.get("/healthz").headers["content-security-policy"]
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_uploads_not_no_store(client) -> None:
    # 公开头像等静态资源不应带 no-store，允许网关/CDN 长缓存。
    response = client.get("/uploads/avatars/does-not-exist.png")
    assert response.status_code == 404
    assert "cache-control" not in response.headers
