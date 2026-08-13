from urllib.parse import parse_qs, urlparse

from app.security.jwt import decode_token
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
    claims = decode_token(access, audience="cli_demo")
    assert claims["sub"]
    assert "openid" in claims["scope"]

    response = client.get(
        "/oauth2/userinfo",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "a@example.com"
    assert data["email_verified"] is True

    id_claims = decode_token(body["id_token"], audience="cli_demo")
    assert id_claims["nonce"] == "n-1"


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
