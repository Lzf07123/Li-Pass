from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_token


def login_as(client, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_admin_required(client, db_session) -> None:
    db_session.add(
        User(
            email="u@example.com",
            password_hash=hash_password("password123"),
            nickname="U",
            role=UserRole.user,
        )
    )
    db_session.commit()
    assert login_as(client, "u@example.com").status_code == 200
    response = client.get("/api/v1/admin/clients")
    assert response.status_code == 403


def test_admin_create_and_reset_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    assert login_as(client, "a@example.com").status_code == 200

    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Demo",
            "redirect_uris": ["http://localhost:3001/callback"],
            "public": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    secret = body["client_secret"]
    assert secret
    stored = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == body["client"]["client_id"])
    )
    assert stored is not None
    assert stored.client_secret_hash == hash_token(secret)

    response = client.post(f"/api/v1/admin/clients/{body['client']['id']}/reset-secret")
    assert response.status_code == 200
    new_secret = response.json()["client_secret"]
    assert new_secret != secret


def test_public_client_has_no_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "SPA",
            "redirect_uris": ["http://localhost:5173/callback"],
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["client_secret"] is None


def test_admin_delete_client(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )

    created = client.post(
        "/api/v1/admin/clients",
        json={"name": "ToDelete", "redirect_uris": ["http://x/cb"]},
    ).json()["client"]

    response = client.delete(f"/api/v1/admin/clients/{created['id']}")
    assert response.status_code == 204
    remaining = client.get("/api/v1/admin/clients").json()
    assert all(item["client_id"] != created["client_id"] for item in remaining)
