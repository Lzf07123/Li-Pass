import pyotp

from tests.helpers import register_and_login


def test_email_2fa_enable_disable(client, captured_email) -> None:
    register_and_login(client, captured_email)
    assert client.post("/api/v1/me/2fa/email/enable").status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is True
    response = client.post(
        "/api/v1/me/2fa/email/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/2fa/status").json()["email_otp_enabled"] is False


def test_totp_setup_enable_and_recovery(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    response = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": code, "secret": secret},
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
