from tests.helpers import authorize_params, create_client, register_and_login


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
