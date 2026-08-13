from sqlalchemy import select

from app.models.audit_log import AuditLog


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
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    assert resp.status_code == 200


def test_register_logs_audit(client, db_session, captured_email) -> None:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "nickname": "New",
            "password": "password123",
        },
    )
    assert resp.status_code == 201
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "user_register")
    )
    assert row is not None
    assert row.category == "auth"


def test_logout_logs_audit(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "logout")
    )
    assert row is not None
    assert row.category == "auth"


def test_profile_update_logs_audit(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.put("/api/v1/me", json={"nickname": "Renamed"})
    assert resp.status_code == 200
    row = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "profile_update")
    )
    assert row is not None
    assert row.category == "user"
