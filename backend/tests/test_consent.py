from tests.helpers import authorize_params, create_client, register_and_login
from app.services.pending_requests import PendingAuthRequest, get_pending_request_store


def get_request_id(client, captured_email, db_session) -> str:
    create_client(db_session)
    register_and_login(client, captured_email)
    response = client.get("/oauth2/authorize", params=authorize_params())
    location = response.headers["location"]
    return location.split("request_id=")[1]


def test_consent_info_and_approve(client, captured_email, db_session) -> None:
    request_id = get_request_id(client, captured_email, db_session)
    response = client.get(f"/api/v1/consent/{request_id}")
    assert response.status_code == 200
    assert response.json()["client"]["name"] == "Demo"
    assert response.json()["scopes"] == ["openid", "profile"]
    assert response.json()["user"]["email"] == "a@example.com"

    response = client.post(f"/api/v1/consent/{request_id}/approve")
    assert response.status_code == 200
    redirect_url = response.json()["redirect_url"]
    assert redirect_url.startswith("http://localhost:3001/callback?code=")
    assert "state=st-1" in redirect_url

    response = client.get("/oauth2/authorize", params=authorize_params())
    assert response.status_code == 302
    assert "code=" in response.headers["location"]


def test_consent_deny(client, captured_email, db_session) -> None:
    request_id = get_request_id(client, captured_email, db_session)
    response = client.post(f"/api/v1/consent/{request_id}/deny")
    assert response.status_code == 200
    assert "error=access_denied" in response.json()["redirect_url"]
    assert "state=st-1" in response.json()["redirect_url"]


def test_consent_requires_session(client, db_session) -> None:
    create_client(db_session)
    response = client.get("/api/v1/consent/whatever")
    assert response.status_code == 401


def test_consent_request_bound_to_originating_user(
    client, captured_email, db_session
) -> None:
    """他人发起的待授权请求不能被当前会话用户批准（防串号授权）。"""
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    pending = PendingAuthRequest(
        client_id=client_model.client_id,
        redirect_uri="http://localhost:3001/callback",
        scope="openid profile",
        state="st-1",
        nonce="n-1",
        code_challenge="c",
        user_id="00000000-0000-0000-0000-000000000000",
    )
    request_id = get_pending_request_store().create(pending)
    response = client.post(f"/api/v1/consent/{request_id}/approve")
    assert response.status_code == 403
