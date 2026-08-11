from sqlalchemy import select

from app.models.user import User


def test_register_verify_updates_user(client, db_session, captured_email) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "A@Example.com", "password": "password123", "nickname": "Alice"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "a@example.com"
    assert body["email_verified"] is False

    code = captured_email.messages[0][2]
    response = client.post(
        "/api/v1/auth/email/verify",
        json={"email": "a@example.com", "code": code},
    )
    assert response.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert user is not None
    assert user.email_verified_at is not None


def test_register_duplicate_email(client, captured_email) -> None:
    payload = {"email": "a@example.com", "password": "password123", "nickname": "Alice"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409


def test_me_requires_session(client) -> None:
    assert client.get("/api/v1/me").status_code == 401
