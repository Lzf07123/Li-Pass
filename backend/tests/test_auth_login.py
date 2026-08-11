from sqlalchemy import select

from app.models.user import User, UserStatus


def register_and_verify(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})


def test_login_logout_flow(client, captured_email) -> None:
    register_and_verify(client, captured_email)

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    assert response.status_code == 200
    assert "portal_session" in response.cookies

    assert client.get("/api/v1/me").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 204
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
    assert response.status_code == 403


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
