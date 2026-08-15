import pyotp

from app.services.rate_limit import get_rate_limiter
from tests.helpers import register_and_login


def enable_email_2fa(client, captured_email) -> None:
    register_and_login(client, captured_email)
    # register_and_login 内部已消耗一次 2FA 邮件发送；
    # 本文件要单独验证登录后的 60 秒重发冷却，先把测试侧计数清零。
    get_rate_limiter().reset("otp_resend_cooldown", "a@example.com")
    get_rate_limiter().reset("otp_send", "a@example.com")
    response = client.post(
        "/api/v1/me/2fa/email/enable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200


def test_email_2fa_login_flow(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    before = len(captured_email.messages)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_2fa"] is True
    challenge_id = body["challenge_id"]
    assert "email_otp" in body["methods"]
    assert "lipass_session" not in response.cookies
    # 进入 2FA 界面不自动发邮件，需用户点击“获取验证码”
    assert body["email_sent"] is False
    assert body["email_status"] == "skipped"
    assert len(captured_email.messages) == before

    response = client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": challenge_id},
    )
    assert response.status_code == 200
    assert len(captured_email.messages) == before + 1
    code = captured_email.messages[-1][2]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": code},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_email_2fa_login_carries_remember_me(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "a@example.com",
            "password": "password123",
            "remember_me": True,
        },
    )
    challenge_id = login.json()["challenge_id"]
    client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": challenge_id},
    )
    code = captured_email.messages[-1][2]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": code},
    )
    assert response.status_code == 200
    assert "Max-Age=2592000" in response.headers["set-cookie"]


def test_email_2fa_resend_has_60s_cooldown(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    challenge_id = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    ).json()["challenge_id"]

    first = client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": challenge_id},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": challenge_id},
    )
    assert second.status_code == 429
    assert "秒后重试" in second.json()["detail"]


def test_totp_login_flow(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": code, "secret": secret, "current_password": "password123"},
    )
    client.post("/api/v1/auth/logout")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.json()["methods"] == ["email_otp", "totp", "recovery"]
    challenge_id = response.json()["challenge_id"]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "challenge_id": challenge_id,
            "method": "totp",
            "code": pyotp.TOTP(secret).now(),
        },
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_recovery_code_login(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    enable = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={
            "code": pyotp.TOTP(secret).now(),
            "secret": secret,
            "current_password": "password123",
        },
    ).json()
    recovery = enable["recovery_codes"][0]
    client.post("/api/v1/auth/logout")
    challenge_id = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    ).json()["challenge_id"]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "recovery", "code": recovery},
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_2fa_verify_attempts_lock(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    challenge_id = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    ).json()["challenge_id"]
    for _ in range(5):
        client.post(
            "/api/v1/auth/2fa/verify",
            json={"challenge_id": challenge_id, "method": "email_otp", "code": "000000"},
        )
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": "000000"},
    )
    assert response.status_code in (400, 404)
