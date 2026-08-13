import base64

from app.models.oauth_client import OAuthClient
from app.security.tokens import hash_token


def auth_header(client_id: str, secret: str) -> dict:
    token = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_public_client_rejected(client, db_session) -> None:
    db_session.add(
        OAuthClient(client_id="cli_pub", name="Pub", redirect_uris=["http://x/cb"])
    )
    db_session.commit()
    response = client.get("/oauth2/client/blocks", headers=auth_header("cli_pub", "x"))
    assert response.status_code == 401


def test_confidential_client_crud(client, db_session) -> None:
    db_session.add(
        OAuthClient(
            client_id="cli_conf",
            client_secret_hash=hash_token("secret123"),
            name="Conf",
            redirect_uris=["http://x/cb"],
        )
    )
    db_session.commit()
    headers = auth_header("cli_conf", "secret123")

    response = client.post(
        "/oauth2/client/blocks",
        headers=headers,
        json={"email": "Bad@Example.com", "reason": "滥用"},
    )
    assert response.status_code == 200
    block_id = response.json()["id"]
    assert response.json()["email"] == "bad@example.com"

    response = client.post(
        "/oauth2/client/blocks",
        headers=headers,
        json={"email": "bad@example.com"},
    )
    assert response.status_code == 409

    response = client.get("/oauth2/client/blocks", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.delete(f"/oauth2/client/blocks/{block_id}", headers=headers)
    assert response.status_code == 204
    assert client.get("/oauth2/client/blocks", headers=headers).json() == []


def test_client_blocks_rate_limited(client, db_session, monkeypatch) -> None:
    from app.core.config import Settings

    db_session.add(
        OAuthClient(
            client_id="cli_conf",
            client_secret_hash=hash_token("secret123"),
            name="Conf",
            redirect_uris=["http://x/cb"],
        )
    )
    db_session.commit()
    settings = Settings(
        _env_file=None,
        client_block_rate_limit=2,
        client_block_rate_window_seconds=3600,
    )
    monkeypatch.setattr(
        "app.api.routes.client_blocks.get_settings", lambda: settings
    )
    headers = auth_header("cli_conf", "secret123")

    for _ in range(2):
        response = client.get("/oauth2/client/blocks", headers=headers)
        assert response.status_code == 200

    response = client.get("/oauth2/client/blocks", headers=headers)
    assert response.status_code == 429
