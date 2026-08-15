import urllib.parse

from sqlalchemy import select

from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from tests.helpers import create_client, register_and_login


def _request_id_from_location(location: str) -> str:
    query = urllib.parse.urlsplit(location).query
    return dict(urllib.parse.parse_qsl(query))["request_id"]


def test_end_session_redirects_to_confirm_page(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    resp = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    assert resp.status_code == 302
    assert "/logout/confirm?request_id=" in resp.headers["location"]


def test_end_session_rejects_unregistered_redirect(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    create_client(db_session, client_id="cli_logout", redirect_uris=["http://x/cb"])
    resp = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://evil.example/",
        },
    )
    assert resp.status_code == 302
    assert "evil.example" not in resp.headers["location"]


def test_end_session_without_portal_session_redirects_back(
    client, db_session
) -> None:
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    resp = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://x/after-logout?state=st-9"


def test_confirm_revokes_session_and_returns_redirect(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    started = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    request_id = _request_id_from_location(started.headers["location"])
    resp = client.post(f"/api/v1/oauth/logout-requests/{request_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["redirect_url"] == "https://x/after-logout?state=st-9"
    assert client.get("/api/v1/me").status_code == 401


def test_cancel_returns_redirect_without_logout(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    started = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    request_id = _request_id_from_location(started.headers["location"])
    resp = client.post(f"/api/v1/oauth/logout-requests/{request_id}/cancel")
    assert resp.status_code == 200
    assert resp.json()["redirect_url"] == "https://x/after-logout?state=st-9"
    assert client.get("/api/v1/me").status_code == 200


def test_discovery_advertises_end_session(client) -> None:
    data = client.get("/.well-known/openid-configuration").json()
    assert data["end_session_endpoint"].endswith("/oauth2/end-session")
    assert data["backchannel_logout_supported"] is True
    assert data["frontchannel_logout_supported"] is False


def test_confirm_dispatches_backchannel_logout(
    client, db_session, captured_email, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after"],
        backchannel_logout_uri="https://x/backchannel",
    )
    user = db_session.scalar(select(User))
    portal = db_session.scalar(select(SessionModel))
    db_session.add(
        OIDCClientSession(
            session_id=portal.id, client_id=oauth_client.id, user_id=user.id
        )
    )
    db_session.commit()
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.oidc.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    started = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_bc",
            "post_logout_redirect_uri": "https://x/after",
        },
    )
    request_id = _request_id_from_location(started.headers["location"])
    resp = client.post(f"/api/v1/oauth/logout-requests/{request_id}/confirm")
    assert resp.status_code == 200
    assert len(calls) == 1
    targets = calls[0]
    assert len(targets) == 1
    assert targets[0].client_id == "cli_bc"
    assert targets[0].sid == str(portal.id)
    assert targets[0].sub == str(user.id)
