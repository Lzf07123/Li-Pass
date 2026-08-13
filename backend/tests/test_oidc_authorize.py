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
