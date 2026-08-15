import pyotp

from tests.helpers import register_and_login


def test_email_2fa_enable_disable(client, captured_email) -> None:
    register_and_login(client, captured_email)
    # 验证邮箱后已默认开启邮箱验证码。
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
    # 开启/关闭都必须提供当前密码或处于 step-up 窗口内
    response = client.post("/api/v1/me/2fa/email/enable", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"
    response = client.post(
        "/api/v1/me/2fa/email/enable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
    assert (
        client.post(
            "/api/v1/me/2fa/email/enable",
            json={"current_password": "wrong-password"},
        ).status_code
        == 400
    )
    # 强制 2FA：邮箱验证码是唯一方案时不允许关闭。
    response = client.post(
        "/api/v1/me/2fa/email/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 400
    assert "至少保留一种二次验证方式" in response.json()["detail"]
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True


def test_totp_setup_enable_and_recovery(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": code, "secret": secret, "current_password": "password123"},
    )
    assert response.status_code == 200
    recovery = response.json()["recovery_codes"]
    assert len(recovery) == 10
    status = client.get("/api/v1/me/2fa/status").json()
    assert status["totp_enabled"] is True
    assert status["recovery_codes_remaining"] == 10

    response = client.post(
        "/api/v1/me/2fa/totp/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["totp_enabled"] is False
