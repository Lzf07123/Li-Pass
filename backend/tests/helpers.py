import base64
import hashlib

from app.models.oauth_client import OAuthClient

TEST_VERIFIER = "v" * 43


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def register_and_login(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})
    client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "password123"},
    )


def create_client(db_session, **overrides) -> OAuthClient:
    values = {
        "client_id": "cli_demo",
        "name": "Demo",
        "redirect_uris": ["http://localhost:3001/callback"],
        "scopes": ["openid", "profile", "email"],
    }
    values.update(overrides)
    client = OAuthClient(**values)
    db_session.add(client)
    db_session.commit()
    return client


def authorize_params(overrides=None) -> dict:
    params = {
        "response_type": "code",
        "client_id": "cli_demo",
        "redirect_uri": "http://localhost:3001/callback",
        "scope": "openid profile",
        "state": "st-1",
        "nonce": "n-1",
        "code_challenge": challenge_for(TEST_VERIFIER),
        "code_challenge_method": "S256",
    }
    if overrides:
        params.update(overrides)
    return params
