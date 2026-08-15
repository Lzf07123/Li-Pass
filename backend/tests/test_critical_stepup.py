import pyotp
from sqlalchemy import select

from app.core.config import Settings
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.services.rate_limit import get_rate_limiter
from tests.helpers import critical_stepup_payload, register_and_login


def _totp_stepup(client, captured_email, secret) -> dict:
    return {
        "current_password": "password123",
        "stepup_method": "totp",
        "stepup_code": pyotp.TOTP(secret).now(),
    }


def test_stepup_send_requires_login(client) -> None:
    assert client.post("/api/v1/me/step-up/send").status_code == 401


def test_stepup_send_delivers_email_code(client, captured_email) -> None:
    register_and_login(client, captured_email)
    # register_and_login 内部已消耗一次验证码发送，清理冷却后再验证发送端点。
    get_rate_limiter().reset("otp_resend_cooldown", "a@example.com")
    get_rate_limiter().reset("otp_send", "a@example.com")
    before = len(captured_email.messages)
    response = client.post("/api/v1/me/step-up/send")
    assert response.status_code == 200
    assert len(captured_email.messages) == before + 1
    assert captured_email.messages[-1][0] == "verification"


def test_delete_requires_password_and_2fa(client, captured_email) -> None:
    register_and_login(client, captured_email)

    missing_all = client.post("/api/v1/me/delete", json={})
    assert missing_all.status_code == 400
    assert missing_all.json()["detail"] == "注销账号必须输入当前密码并完成二次验证"

    missing_2fa = client.post(
        "/api/v1/me/delete",
        json={"current_password": "password123"},
    )
    assert missing_2fa.status_code == 400
    assert missing_2fa.json()["detail"] == "请选择一种二次验证方式并输入验证码"

    wrong_password = client.post(
        "/api/v1/me/delete",
        json=critical_stepup_payload(
            client,
            captured_email,
            "a@example.com",
            password="wrong-password",
        ),
    )
    assert wrong_password.status_code == 400
    assert wrong_password.json()["detail"] == "当前密码错误"

    wrong_code = client.post(
        "/api/v1/me/delete",
        json={
            "current_password": "password123",
            "stepup_method": "email_otp",
            "stepup_code": "000000",
        },
    )
    assert wrong_code.status_code == 400
    assert wrong_code.json()["detail"] == "二次验证码无效"


def test_delete_succeeds_with_email_2fa(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/me/delete",
        json=critical_stepup_payload(client, captured_email, "a@example.com"),
    )
    assert response.status_code == 200


def test_delete_succeeds_with_totp(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    assert (
        client.post(
            "/api/v1/me/2fa/totp/enable",
            json={
                "code": pyotp.TOTP(secret).now(),
                "secret": secret,
                "current_password": "password123",
            },
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/me/delete",
        json=_totp_stepup(client, captured_email, secret),
    )
    assert response.status_code == 200


def test_window_does_not_exempt_critical_delete(client, captured_email) -> None:
    register_and_login(client, captured_email)
    # 密码复核开窗（30 分钟）后，注销仍必须当场双因素复核。
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )
    response = client.post("/api/v1/me/delete", json={})
    assert response.status_code == 400
    assert response.json()["detail"] == "注销账号必须输入当前密码并完成二次验证"


def test_critical_2fa_failures_rate_limited(
    client, captured_email, db_session, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    settings = Settings(_env_file=None, stepup_rate_limit=2)
    monkeypatch.setattr("app.services.stepup.get_settings", lambda: settings)

    for _ in range(2):
        response = client.post(
            "/api/v1/me/delete",
            json={
                "current_password": "password123",
                "stepup_method": "email_otp",
                "stepup_code": "000000",
            },
        )
        assert response.status_code == 400
    response = client.post(
        "/api/v1/me/delete",
        json={
            "current_password": "password123",
            "stepup_method": "email_otp",
            "stepup_code": "000000",
        },
    )
    assert response.status_code == 429
    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "stepup_2fa_failed")
    ).all()
    assert len(logs) == 3


def test_admin_delete_succeeds_with_email_2fa(
    client, captured_email, db_session
) -> None:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    target = User(
        email="bob@example.com",
        password_hash="x",
        nickname="Bob",
    )
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    response = client.post(
        f"/api/v1/admin/users/{target.id}/delete",
        json=critical_stepup_payload(
            client, captured_email, "admin@example.com"
        ),
    )
    assert response.status_code == 200
