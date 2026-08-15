from sqlalchemy import select

from app.models.user import User, UserRole
from app.security.passwords import hash_password
from tests.helpers import login_with_email_2fa, register_and_login


def test_login_rate_limit(client, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")
    for _ in range(10):
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "wrong"},
        )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrong"},
    )
    assert response.status_code == 429


def test_audit_logs_written_and_listed(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    response = client.get("/api/v1/admin/audit-logs")
    assert response.status_code == 200
    assert any(item["action"] == "login" for item in response.json())


def test_admin_reset_twofa(client, db_session, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/me/2fa/email/enable")
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    user.role = UserRole.admin
    db_session.commit()
    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-2fa",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    # 2FA 重置会撤销全部会话，需要重新登录后再查状态；
    # 强制 2FA 下重置恢复默认邮箱验证码（登录兜底也保证该不变式）。
    login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
