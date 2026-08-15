from urllib.parse import parse_qs, urlparse
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.models.oidc_client_session import OIDCClientSession
from app.models.user import User
from app.security.jwt import decode_token, userinfo_audience
from tests.helpers import TEST_VERIFIER, authorize_params, create_client, register_and_login


def get_code(client, captured_email, db_session) -> str:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"scope": "openid profile email"}),
    )
    location = response.headers["location"]
    request_id = location.split("request_id=")[1]
    response = client.post(f"/api/v1/consent/{request_id}/approve")
    return parse_qs(urlparse(response.json()["redirect_url"]).query)["code"][0]


def exchange(client, code: str, verifier: str = TEST_VERIFIER) -> dict:
    return client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_demo",
            "code_verifier": verifier,
        },
    )


def test_token_and_userinfo_flow(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    response = exchange(client, code)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "Bearer"
    access = body["access_token"]
    claims = decode_token(access, audience=userinfo_audience(get_settings()))
    assert claims["sub"]
    assert "openid" in claims["scope"]
    assert claims["aud"] == "http://localhost:8000/oauth2/userinfo"

    user = db_session.scalar(select(User))
    assert user is not None
    user.avatar_url = "/uploads/avatars/u/avatar.jpg"
    db_session.commit()

    response = client.get(
        "/oauth2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "a@example.com"
    assert data["email_verified"] is True
    assert data["picture"] == (
        "http://localhost:8000/uploads/avatars/u/avatar.jpg"
    )

    id_claims = decode_token(body["id_token"], audience="cli_demo")
    assert id_claims["nonce"] == "n-1"
    assert id_claims["aud"] == "cli_demo"


def test_id_token_contains_sid_and_records_client_session(
    client, captured_email, db_session
) -> None:
    code = get_code(client, captured_email, db_session)
    response = exchange(client, code)
    assert response.status_code == 200
    claims = decode_token(response.json()["id_token"], audience="cli_demo")
    assert claims["sid"]
    link = db_session.scalar(select(OIDCClientSession))
    assert link is not None
    assert link.sid == claims["sid"]
    assert link.client_id is not None


def test_reexchange_revives_revoked_client_session_link(
    client, captured_email, db_session
) -> None:
    code = get_code(client, captured_email, db_session)
    assert exchange(client, code).status_code == 200
    link = db_session.scalar(select(OIDCClientSession))
    assert link is not None
    link.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    # 已有授权同意：再次 authorize 直接跳回回调，换取新授权码。
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"scope": "openid profile email"}),
    )
    assert response.status_code == 302
    code2 = parse_qs(urlparse(response.headers["location"]).query)["code"][0]
    assert exchange(client, code2).status_code == 200
    db_session.expire_all()
    revived = db_session.scalar(select(OIDCClientSession))
    assert revived is not None
    assert revived.revoked_at is None


def test_code_is_single_use(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    assert exchange(client, code).status_code == 200
    assert exchange(client, code).status_code == 400


def test_wrong_pkce_verifier_rejected(client, captured_email, db_session) -> None:
    code = get_code(client, captured_email, db_session)
    assert exchange(client, code, verifier="w" * 43).status_code == 400


def test_discovery_and_jwks(client) -> None:
    discovery = client.get("/.well-known/openid-configuration").json()
    assert discovery["issuer"] == "http://localhost:8000"
    assert discovery["response_types_supported"] == ["code"]
    jwks = client.get("/oauth2/jwks").json()
    assert jwks["keys"][0]["alg"] == "RS256"


def test_userinfo_respects_scope(client, captured_email, db_session) -> None:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get(
        "/oauth2/authorize",
        params=authorize_params({"scope": "openid"}),
    )
    location = response.headers["location"]
    request_id = location.split("request_id=")[1]
    response = client.post(f"/api/v1/consent/{request_id}/approve")
    code = parse_qs(urlparse(response.json()["redirect_url"]).query)["code"][0]
    body = exchange(client, code)
    assert body.status_code == 200

    userinfo = client.get(
        "/oauth2/userinfo",
        headers={"Authorization": f"Bearer {body.json()['access_token']}"},
    )
    assert userinfo.status_code == 200
    assert "email" not in userinfo.json()
    assert "nickname" not in userinfo.json()
