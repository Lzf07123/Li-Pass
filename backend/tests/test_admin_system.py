from sqlalchemy import select

from app.models.audit_log import AuditLog
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


def test_admin_system_requires_auth(client) -> None:
    response = client.get("/api/v1/admin/system")
    assert response.status_code == 401


def test_admin_system_rejects_non_admin(client, db_session) -> None:
    db_session.add(
        User(
            email="user@example.com",
            password_hash=hash_password("password123"),
            nickname="User",
            role=UserRole.user,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    response = client.get("/api/v1/admin/system")
    assert response.status_code == 403


def test_admin_system_returns_metrics(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.get("/api/v1/admin/system")
    assert response.status_code == 200
    body = response.json()

    assert body["collected_at"]
    assert body["app"]["name"]
    assert body["app"]["environment"] == "development"
    assert body["app"]["python_version"]
    assert body["app"]["fastapi_version"]

    host = body["host"]
    assert host["hostname"]
    assert host["system"]
    assert isinstance(host["cpu_cores"], int) and host["cpu_cores"] >= 1

    memory = body["memory"]
    assert memory["total_bytes"] > 0
    assert memory["used_bytes"] >= 0
    assert 0 <= memory["percent"] <= 100
    assert memory["process_rss_bytes"] > 0

    disk = body["disk"]
    assert disk["total_bytes"] > 0
    assert 0 <= disk["percent"] <= 100

    assert body["uptime"]["process_seconds"] >= 0
    assert body["services"]["database"] == "ok"
    assert body["services"]["redis"] == "unused"


def test_admin_system_access_is_audited(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.get("/api/v1/admin/system")
    assert response.status_code == 200

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_view_system")
    ).all()
    assert len(logs) == 1
    assert logs[0].category == "admin_settings"
