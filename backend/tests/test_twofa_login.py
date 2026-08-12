import pyotp

from tests.helpers import register_and_login


def enable_email_2fa(client, captured_email) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/me/2fa/email/enable")


def test_email_2fa_login_flow(client, captured_email) -> None:
    enable_email_2fa(client, captured_email)
    client.post("/api/v1/auth/logout")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requires_2fa"] is True
    challenge_id = body["challenge_id"]
    assert "email_otp" in body["methods"]
    assert "portal_session" not in response.cookies

    code = captured_email.messages[-1][2]
    response = client.post(
        "/api/v1/auth/2fa/verify",
        json={"challenge_id": challenge_id, "method": "email_otp", "code": code},
    )
    assert response.status_code == 200
    assert "portal_session" in response.cookies


def test_totp_login_flow(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/api/v1/me/2fa/totp/enable", json={"code": code, "secret": secret})
    client.post("/api/v1/auth/logout")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.json()["methods"] == ["totp", "recovery"]
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
    assert "portal_session" in response.cookies


def test_recovery_code_login(client, captured_email) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]
    enable = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={"code": pyotp.TOTP(secret).now(), "secret": secret},
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
    assert "portal_session" in response.cookies


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
