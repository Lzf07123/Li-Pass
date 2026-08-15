from datetime import datetime, timedelta, timezone

import pyotp
from sqlalchemy import select

from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import generate_token, hash_token
from tests.helpers import login_with_email_2fa, register_and_login


def test_verified_user_login_requires_email_2fa(
    client, captured_email
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "Alice",
        },
    )
    code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/auth/email/verify",
            json={"email": "a@example.com", "code": code},
        ).status_code
        == 200
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    body = login.json()
    assert body["requires_2fa"] is True
    assert "email_otp" in body["methods"]
    assert "lipass_session" not in login.cookies

    response = login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies


def test_login_fallback_auto_enables_email_2fa(
    client, captured_email, db_session
) -> None:
    user = User(
        email="legacy@example.com",
        password_hash=hash_password("password123"),
        nickname="Legacy",
        email_verified_at=datetime.now(timezone.utc),
    )
    db_session.add(user)
    db_session.commit()

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "legacy@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["requires_2fa"] is True
    assert "email_otp" in login.json()["methods"]

    db_session.refresh(user)
    assert user.email_otp_enabled is True
    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "2fa_email_auto_enabled")
    ).all()
    assert len(logs) == 1
    assert logs[0].category == "2fa"


def test_invite_registration_enables_email_2fa(client, db_session) -> None:
    token = generate_token()
    db_session.add(
        AccountInvite(
            email="invited@example.com",
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite/register",
        json={
            "token": token,
            "nickname": "Invited",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    user = db_session.scalar(
        select(User).where(User.email == "invited@example.com")
    )
    assert user is not None
    assert user.email_verified_at is not None
    assert user.email_otp_enabled is True


def test_admin_created_account_enables_email_2fa(client, db_session) -> None:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )

    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "newbie@example.com",
            "nickname": "Newbie",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    user = db_session.scalar(
        select(User).where(User.email == "newbie@example.com")
    )
    assert user is not None
    assert user.email_otp_enabled is True


def test_unverified_user_login_stays_1fa(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "Alice",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json().get("requires_2fa") is not True


def test_cannot_disable_email_2fa_when_it_is_last(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/me/2fa/email/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "至少保留一种二次验证方式，请先开启 TOTP 认证器"


def test_cannot_disable_totp_when_it_is_last(client, captured_email) -> None:
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
    # TOTP 与邮箱共存时，可以关闭邮箱验证码。
    assert (
        client.post(
            "/api/v1/me/2fa/email/disable",
            json={"current_password": "password123"},
        ).status_code
        == 200
    )
    # 现在 TOTP 是唯一方案，关闭被拒。
    response = client.post(
        "/api/v1/me/2fa/totp/disable",
        json={"current_password": "password123"},
    )
    assert response.status_code == 400
    assert "至少保留一种二次验证方式" in response.json()["detail"]


def test_admin_reset_twofa_restores_default_email(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
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
    user.role = UserRole.admin
    db_session.commit()

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-2fa",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    db_session.refresh(user)
    assert user.email_otp_enabled is True
    assert user.totp_secret_encrypted is None
    codes = db_session.scalars(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ).all()
    assert codes == []
