from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.trusted_device import TrustedDevice
from app.services.rate_limit import get_rate_limiter
from tests.helpers import register_and_login


def _complete_login_2fa(client, captured_email, trust_device: bool = False):
    get_rate_limiter().reset("otp_resend_cooldown", "a@example.com")
    get_rate_limiter().reset("otp_send", "a@example.com")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["requires_2fa"] is True
    client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": body["challenge_id"]},
    )
    code = captured_email.messages[-1][2]
    return client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "challenge_id": body["challenge_id"],
            "method": "email_otp",
            "code": code,
            "trust_device": trust_device,
        },
    )


def test_trusted_device_grants_and_skips_login_2fa(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")

    verify = _complete_login_2fa(client, captured_email, trust_device=True)
    assert verify.status_code == 200
    assert "lipass_trusted_device" in client.cookies
    device = db_session.scalar(select(TrustedDevice))
    assert device is not None

    client.post("/api/v1/auth/logout")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert "requires_2fa" not in login.json()
    assert "lipass_session" in client.cookies

    actions = set(
        db_session.scalars(select(AuditLog.action)).all()
    )
    assert "trusted_device_granted" in actions
    assert "2fa_trusted_skip" in actions


def test_trusted_device_does_not_bypass_password(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")
    _complete_login_2fa(client, captured_email, trust_device=True)
    client.post("/api/v1/auth/logout")

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_without_trust_next_login_still_requires_2fa(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    client.post("/api/v1/auth/logout")
    verify = _complete_login_2fa(client, captured_email, trust_device=False)
    assert verify.status_code == 200
    assert "lipass_trusted_device" not in client.cookies

    client.post("/api/v1/auth/logout")
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["requires_2fa"] is True
