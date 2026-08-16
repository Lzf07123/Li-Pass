from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from app.models.user_consent import UserConsent
from app.security.passwords import verify_password
from tests.helpers import (
    authorize_params,
    create_client,
    login_with_email_2fa,
    register_and_login,
)


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


def test_external_avatar_http_rejected_in_production(monkeypatch) -> None:
    import pytest
    from pydantic import ValidationError

    from app.schemas.auth import ProfileUpdate

    class FakeSettings:
        environment = "production"

    monkeypatch.setattr("app.schemas.auth.get_settings", lambda: FakeSettings())
    with pytest.raises(ValidationError):
        ProfileUpdate(avatar_url="http://a.png")
    assert ProfileUpdate(avatar_url="https://a.png").avatar_url == "https://a.png"


def test_update_profile_email_notifications(client, captured_email) -> None:
    register_and_login(client, captured_email)
    me = client.get("/api/v1/me").json()
    assert me["email_notifications"] is True

    updated = client.put(
        "/api/v1/me", json={"email_notifications": False}
    ).json()
    assert updated["email_notifications"] is False
    again = client.put("/api/v1/me", json={"nickname": "New"}).json()
    assert again["email_notifications"] is False  # 未传字段不重置
    assert again["nickname"] == "New"


def test_phone_bind_demo(client, captured_email) -> None:
    register_and_login(client, captured_email)
    assert client.post("/api/v1/me/phone/bind/send").status_code == 200
    code = captured_email.messages[-1][2]
    response = client.post(
        "/api/v1/me/phone/bind",
        json={"phone": "+8613800000000", "code": code},
    )
    assert response.status_code == 200
    assert response.json()["phone"] == "+8613800000000"


def test_sessions_list_and_revoke(client, captured_email) -> None:
    register_and_login(client, captured_email)
    sessions = client.get("/api/v1/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    current_id = sessions[0]["id"]
    assert client.delete(f"/api/v1/sessions/{current_id}").status_code == 400

    login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    sessions = client.get("/api/v1/sessions").json()
    other = next(s for s in sessions if not s["current"])
    assert client.delete(f"/api/v1/sessions/{other['id']}").status_code == 204
    assert len(client.get("/api/v1/sessions").json()) == 1


def test_sessions_revoke_all_keeps_current(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    login_with_email_2fa(client, captured_email, "a@example.com", "password123")
    login_with_email_2fa(client, captured_email, "a@example.com", "password123")
    # 三次登录产生 3 个会话：当前 + 2 个历史设备
    assert len(client.get("/api/v1/sessions").json()) == 3

    response = client.post("/api/v1/sessions/revoke-all")
    assert response.status_code == 200
    assert response.json() == {"revoked": 2}

    sessions = client.get("/api/v1/sessions").json()
    assert len(sessions) == 1
    assert sessions[0]["current"] is True

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "session_revoke_all")
    )
    assert audit is not None
    assert audit.detail == {"count": 2}


def test_sessions_revoke_all_requires_auth(client) -> None:
    assert client.post("/api/v1/sessions/revoke-all").status_code == 401


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


def test_apps_plaza_reports_active_sessions(
    client, captured_email, db_session
) -> None:
    client_model = create_client(
        db_session, logout_uri="http://localhost:3001/logout"
    )
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    portal = db_session.scalar(select(SessionModel))
    db_session.add(
        UserConsent(
            user_id=user.id, client_id=client_model.id, scopes=["openid"]
        )
    )
    db_session.commit()

    assert client.get("/api/v1/apps").json()[0]["active_sessions"] == 0
    db_session.add(
        OIDCClientSession(
            session_id=portal.id, client_id=client_model.id, user_id=user.id
        )
    )
    db_session.commit()
    assert client.get("/api/v1/apps").json()[0]["active_sessions"] == 1
