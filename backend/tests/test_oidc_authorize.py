from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.models.user import User
from app.models.user_consent import UserConsent

from tests.helpers import authorize_params, create_client, register_and_login


def test_authorize_without_session_redirects_to_login(client, db_session) -> None:
    create_client(db_session)
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/login?next=")
    assert "%2Foauth2%2Fauthorize%3F" in location


def test_authorize_with_session_redirects_to_consent(client, db_session, captured_email) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:5173/consent?request_id=")


def test_authorize_with_existing_consent_auto_approves(client, db_session, captured_email) -> None:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(
        select(User).where(User.email == "a@example.com")
    )
    db_session.add(
        UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid", "profile"])
    )
    db_session.commit()
    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:3001/callback?code=")
    assert "state=st-1" in location


def test_authorize_redirect_with_query_string_appends_params(
    client, db_session, captured_email
) -> None:
    client_model = create_client(
        db_session,
        redirect_uris=["http://localhost:3001/callback?x=1"],
    )
    register_and_login(client, captured_email)
    user = db_session.scalar(
        select(User).where(User.email == "a@example.com")
    )
    db_session.add(
        UserConsent(
            user_id=user.id,
            client_id=client_model.id,
            scopes=["openid", "profile"],
        )
    )
    db_session.commit()
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params(
            {"redirect_uri": "http://localhost:3001/callback?x=1"}
        ),
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://localhost:3001/callback?x=1&code=")
    assert "state=st-1" in location


def test_authorize_rejects_oversized_nonce(client, db_session, captured_email) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"nonce": "n" * 300}),
    )
    assert response.status_code == 422


def test_authorize_invalid_redirect_uri(client, db_session) -> None:
    create_client(db_session)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"redirect_uri": "http://evil.example/cb"}),
    )
    assert response.status_code == 302
    assert response.headers["location"].startswith(
        "http://localhost:5173/?error=invalid_redirect_uri"
    )


def test_authorize_requires_pkce(client, db_session, captured_email) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"code_challenge": None}),
    )
    assert response.status_code == 302
    assert "error=invalid_request" in response.headers["location"]


def test_authorize_requires_verified_email_for_email_scope(
    client, db_session, captured_email
) -> None:
    create_client(db_session)
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "unverified@example.com",
            "password": "password123",
            "nickname": "Unverified",
        },
    )
    client.post(
        "/api/v1/auth/login",
        json={"email": "unverified@example.com", "password": "password123"},
    )
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"scope": "openid email"}),
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith(
        "http://localhost:5173/verify-email?email=unverified%40example.com&next="
    )
    # 验证页应保留原授权请求：验证成功后前端据此回到授权流程并最终跳回应用。
    next_url = parse_qs(urlparse(location).query)["next"][0]
    assert next_url.startswith("http://localhost:8000/oauth2/authorize?")
    assert "code_challenge=" in next_url
    assert "scope=openid+email" in next_url
