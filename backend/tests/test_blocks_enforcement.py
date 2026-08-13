from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent
from tests.helpers import TEST_VERIFIER, authorize_params, create_client, register_and_login


def block_user(db_session, client_model, user, email=None) -> None:
    db_session.add(
        ClientUserBlock(
            client_id=client_model.id,
            user_id=user.id if user else None,
            email=email or (user.email if user else None),
            reason="滥用",
        )
    )
    db_session.commit()


def get_code(client, captured_email, db_session, with_consent=True) -> str:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    if with_consent:
        user = db_session.scalar(select(User).where(User.email == "a@example.com"))
        db_session.add(
            UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid", "profile"])
        )
        db_session.commit()
    response = client.get("/oauth2/authorize", params=authorize_params())
    return parse_qs(urlparse(response.headers["location"]).query)["code"][0]


def test_authorize_blocked_user_gets_access_denied(client, captured_email, db_session) -> None:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    block_user(db_session, client_model, user)

    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    location = response.headers["location"]
    assert "error=access_denied" in location
    assert "error_description=account_blocked" in location


def test_userinfo_blocked_after_token(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    token_response = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": TEST_VERIFIER,
        },
    )
    assert token_response.status_code == 200
    access = token_response.json()["access_token"]
    assert (
        client.get("/oauth2/userinfo", headers={"Authorization": f"Bearer {access}"}).status_code
        == 200
    )

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    client_model = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == "cli_demo")
    )
    block_user(db_session, client_model, user)
    response = client.get("/oauth2/userinfo", headers={"Authorization": f"Bearer {access}"})
    assert response.status_code == 403


def test_token_blocked(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    client_model = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == "cli_demo")
    )
    block_user(db_session, client_model, user)
    response = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": TEST_VERIFIER,
        },
    )
    assert response.status_code == 403
