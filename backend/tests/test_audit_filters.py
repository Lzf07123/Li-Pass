from datetime import datetime, timedelta, timezone

from app.services.audit import log_audit


def _login_admin(client, db_session):
    from app.models.user import User, UserRole
    from app.security.passwords import hash_password

    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )


def test_audit_list_filters_by_category(client, db_session) -> None:
    _login_admin(client, db_session)
    log_audit(db_session, "user", "u1", "login", category="auth")
    log_audit(db_session, "user", "u1", "login_failed", category="security")
    resp = client.get("/api/v1/admin/audit-logs?category=security")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["action"] == "login_failed"
    assert items[0]["category"] == "security"


def test_audit_list_filters_by_actor_and_time(client, db_session) -> None:
    _login_admin(client, db_session)
    now = datetime.now(timezone.utc)
    log_audit(db_session, "user", "u1", "login", category="auth")
    log_audit(db_session, "user", "u2", "login", category="auth")
    start = (now - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = client.get(
        f"/api/v1/admin/audit-logs?actor_id=u1&start={start}&end={end}"
    )
    assert resp.status_code == 200
    items = resp.json()
    assert all(item["actor_id"] == "u1" for item in items)


def test_audit_list_include_ip_location(client, db_session, monkeypatch) -> None:
    from app.api.routes import admin_users as routes

    monkeypatch.setattr(
        routes, "describe_ip", lambda ip: "广东省 深圳市", raising=False
    )
    _login_admin(client, db_session)
    log_audit(db_session, "user", "u1", "login", category="auth", ip="203.0.113.7")
    items = client.get("/api/v1/admin/audit-logs").json()
    assert items[0]["ip_location"] == "广东省 深圳市"
