from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from tests.helpers import register_and_login


def _login_admin(client, db_session) -> None:
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


def test_site_settings_public_registration_switch(
    client, db_session, captured_email
) -> None:
    _login_admin(client, db_session)

    # 默认跟随环境变量（true）
    assert client.get("/api/v1/admin/settings").json() == {
        "public_registration_enabled": True
    }
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }

    # 管理员关闭公开注册
    response = client.put(
        "/api/v1/admin/settings",
        json={"public_registration_enabled": False},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": False
    }
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "blocked@example.com",
                "password": "password123",
                "nickname": "Blocked",
            },
        ).status_code
        == 403
    )

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_update_site_setting")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["value"] is False

    # 重新开启后恢复公开注册
    assert (
        client.put(
            "/api/v1/admin/settings",
            json={"public_registration_enabled": True},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }


def test_non_admin_cannot_access_site_settings(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    assert client.get("/api/v1/admin/settings").status_code == 403
    assert (
        client.put(
            "/api/v1/admin/settings",
            json={"public_registration_enabled": False},
        ).status_code
        == 403
    )
