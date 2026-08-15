from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.session import Session as SessionModel
from app.models.user import User, UserStatus
from tests.helpers import login_with_email_2fa


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def register_and_verify(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})


def test_login_logout_flow(client, captured_email) -> None:
    register_and_verify(client, captured_email)

    response = login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert response.status_code == 200
    assert "lipass_session" in response.cookies

    assert client.get("/api/v1/me").status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert logout.json() == {"redirect_to": None}
    assert client.get("/api/v1/me").status_code == 401


def test_login_remember_me_controls_cookie_and_ttl(
    client, captured_email, db_session
) -> None:
    register_and_verify(client, captured_email)

    default = login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert default.status_code == 200
    assert "Max-Age=" not in default.headers["set-cookie"]
    client.post("/api/v1/auth/logout")

    remembered = login_with_email_2fa(
        client,
        captured_email,
        "a@example.com",
        "password123",
        remember_me=True,
    )
    assert remembered.status_code == 200
    assert "Max-Age=2592000" in remembered.headers["set-cookie"]

    sessions = db_session.scalars(
        select(SessionModel).order_by(SessionModel.created_at.asc())
    ).all()
    assert len(sessions) == 2
    now = datetime.now(timezone.utc)
    assert _as_utc(sessions[0].expires_at) - now < timedelta(days=2)
    assert _as_utc(sessions[1].expires_at) - now > timedelta(days=29)


def test_logout_deletes_cookie_with_matching_attributes(client, captured_email) -> None:
    register_and_verify(client, captured_email)
    login = login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert "lipass_session" in login.cookies
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=lax" in login.headers["set-cookie"]

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    delete_header = logout.headers["set-cookie"]
    assert "lipass_session=" in delete_header
    assert "Max-Age=0" in delete_header
    assert "HttpOnly" in delete_header
    assert "SameSite=lax" in delete_header


def test_legacy_portal_session_cookie_still_authenticates(
    client, captured_email
) -> None:
    register_and_verify(client, captured_email)
    login = login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert login.status_code == 200
    token = login.cookies.get("lipass_session")
    assert token
    client.cookies.clear()
    client.cookies.set("portal_session", token)
    assert client.get("/api/v1/me").status_code == 200
    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    delete_headers = logout.headers.get_list("set-cookie")
    assert any("lipass_session=" in h for h in delete_headers)
    assert any("portal_session=" in h for h in delete_headers)
    assert client.get("/api/v1/me").status_code == 401


def test_login_wrong_password(client, captured_email) -> None:
    register_and_verify(client, captured_email)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrongpass"},
    )
    assert response.status_code == 401


def test_disabled_user_cannot_login(client, db_session, captured_email) -> None:
    register_and_verify(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    user.status = UserStatus.disabled
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    # 与密码错误统一响应，避免泄露账号状态。
    assert response.status_code == 401


def test_unverified_user_can_login_but_flagged(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert response.json()["email_verified"] is False


def test_session_idle_timeout_revokes(client, db_session, captured_email) -> None:
    register_and_verify(client, captured_email)
    assert (
        login_with_email_2fa(
            client, captured_email, "a@example.com", "password123"
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me").status_code == 200

    session = db_session.scalar(select(SessionModel))
    session.last_used_at = datetime.now(timezone.utc) - timedelta(days=8)
    db_session.commit()

    assert client.get("/api/v1/me").status_code == 401
    db_session.refresh(session)
    assert session.revoked_at is not None
