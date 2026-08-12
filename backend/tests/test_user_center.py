from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent
from app.security.passwords import verify_password
from tests.helpers import authorize_params, create_client, register_and_login


def test_update_profile_and_password(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    response = client.put(
        "/api/v1/me",
        json={"nickname": "NewName", "avatar_url": "http://a.png"},
    )
    assert response.status_code == 200
    assert response.json()["nickname"] == "NewName"

    response = client.post(
        "/api/v1/me/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
    )
    assert response.status_code == 200
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert verify_password("newpassword456", user.password_hash)


def test_phone_bind_demo(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.post("/api/v1/me/phone/bind", json={"phone": "+8613800000000"})
    assert response.status_code == 200
    assert response.json()["phone"] == "+8613800000000"


def test_sessions_list_and_revoke(client, captured_email) -> None:
    register_and_login(client, captured_email)
    sessions = client.get("/api/v1/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    current_id = sessions[0]["id"]
    assert client.delete(f"/api/v1/sessions/{current_id}").status_code == 400

    client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )
    sessions = client.get("/api/v1/sessions").json()
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/v1/sessions/{other['id']}").status_code == 204
    assert len(client.get("/api/v1/sessions").json()) == 1


def test_apps_plaza_lists_consented(client, captured_email, db_session) -> None:
    create_client(db_session, home_url="http://localhost:3001")
    register_and_login(client, captured_email)
    assert client.get("/api/v1/apps").json() == []

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    client_model = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == "cli_demo")
    )
    db_session.add(
        UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid"])
    )
    db_session.commit()

    apps = client.get("/api/v1/apps").json()
    assert len(apps) == 1
    assert apps[0]["client_id"] == "cli_demo"
    assert apps[0]["home_url"] == "http://localhost:3001"


def test_apps_plaza_revoke_consent(client, captured_email, db_session) -> None:
    client_model = create_client(db_session, logout_uri="http://localhost:3001/logout")
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(
        UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid"])
    )
    db_session.commit()
    assert len(client.get("/api/v1/apps").json()) == 1

    response = client.delete("/api/v1/apps/cli_demo")
    assert response.status_code == 200
    assert response.json()["logout_uri"] == "http://localhost:3001/logout"
    assert client.get("/api/v1/apps").json() == []

    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    assert "/consent?request_id=" in response.headers["location"]
