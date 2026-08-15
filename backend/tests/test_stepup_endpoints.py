from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.passwords import verify_password
from tests.helpers import register_and_login


def test_twofa_enable_disable_without_password_in_window(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )

    assert client.post("/api/v1/me/2fa/email/enable", json={}).status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
    assert client.post("/api/v1/me/2fa/email/disable", json={}).status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is False


def test_change_password_without_current_password_in_window(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )

    response = client.post(
        "/api/v1/me/password", json={"new_password": "newpassword456"}
    )
    assert response.status_code == 200
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert verify_password("newpassword456", user.password_hash)
    # 改密后其它会话吊销，当前会话的复核窗口仍有效。
    assert client.get("/api/v1/me/step-up").json()["active"] is True


def test_change_password_without_window_requires_stepup(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/me/password", json={"new_password": "newpassword456"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"


def test_delete_account_without_password_in_window(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )
    assert client.post("/api/v1/me/delete", json={}).status_code == 200


def test_delete_account_without_window_requires_stepup(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    response = client.post("/api/v1/me/delete", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"


def test_expired_window_requires_stepup_and_logs_audit(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )
    session = db_session.scalar(select(SessionModel))
    session.stepup_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    response = client.post("/api/v1/me/2fa/email/enable", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "stepup_required")
    ).all()
    assert len(logs) == 1
    assert logs[0].category == "security"


def test_wrong_password_still_rejected_inside_window(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/me/password",
        json={"current_password": "wrong", "new_password": "newpassword456"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "当前密码错误"
