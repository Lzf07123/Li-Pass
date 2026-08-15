from app.core.config import Settings
from tests.helpers import login_with_email_2fa, register_and_login


def test_twofa_verify_success_does_not_consume_rate_limit(
    client, captured_email, monkeypatch
) -> None:
    """成功消费 2FA 验证码不应计入限流：连续成功登录不触发 429。"""
    settings = Settings(_env_file=None, twofa_verify_rate_limit=1)
    monkeypatch.setattr("app.api.routes.auth.settings", settings)
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")

    for _ in range(2):
        response = login_with_email_2fa(
            client, captured_email, "a@example.com", "password123"
        )
        assert response.status_code == 200
        client.post("/api/v1/auth/logout")


def test_email_verify_success_does_not_consume_rate_limit(
    client, monkeypatch
) -> None:
    """成功消费邮箱验证码不应计入限流：同一邮箱连续成功不触发 429。"""
    settings = Settings(_env_file=None, email_verify_rate_limit=1)
    monkeypatch.setattr("app.api.routes.auth.settings", settings)
    monkeypatch.setattr(
        "app.api.routes.auth.verify_otp",
        lambda db, purpose, target, code: True,
    )
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "A",
        },
    )
    for _ in range(2):
        response = client.post(
            "/api/v1/auth/email/verify",
            json={"email": "a@example.com", "code": "123456"},
        )
        assert response.status_code == 200
