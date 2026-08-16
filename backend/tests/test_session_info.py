from tests.helpers import register_and_login
from app.core.config import get_settings


def test_me_session_requires_auth(client) -> None:
    assert client.get("/api/v1/me/session").status_code == 401


def test_me_session_returns_idle_info(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.get("/api/v1/me/session")
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"]
    assert body["expires_at"]
    assert body["last_used_at"]
    assert body["idle_limit_minutes"] == get_settings().session_idle_minutes
    assert body["idle_remaining_seconds"] > 0
    assert body["absolute_remaining_seconds"] > 0


def test_me_includes_session_lifecycle(client, captured_email) -> None:
    register_and_login(client, captured_email)
    body = client.get("/api/v1/me").json()
    assert body["session"]["session_id"]
    assert body["session"]["idle_limit_minutes"] == (
        get_settings().session_idle_minutes
    )
