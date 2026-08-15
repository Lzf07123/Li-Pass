from datetime import datetime, timedelta, timezone
from urllib.parse import unquote

from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.tokens import generate_token, hash_token
from app.services.federated_logout import build_logout_funnel
from tests.helpers import create_client, register_and_login


def test_build_logout_funnel_nests_next_chain() -> None:
    chain = build_logout_funnel(
        ["https://a.example/logout", "https://b.example/logout"],
        "http://localhost:5173/login",
    )
    assert chain.startswith("https://a.example/logout?next=")
    decoded = unquote(unquote(chain))
    assert "https://b.example/logout?next=http://localhost:5173/login" in decoded


def test_build_logout_funnel_handles_existing_query_string() -> None:
    chain = build_logout_funnel(
        ["https://a.example/logout?lang=zh"], "http://localhost:5173/login"
    )
    decoded = unquote(chain)
    assert decoded == (
        "https://a.example/logout?lang=zh&next=http://localhost:5173/login"
    )


def test_portal_logout_returns_funnel_for_clients_without_backchannel(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    oauth_client = create_client(
        db_session,
        client_id="cli_funnel",
        redirect_uris=["http://x/cb"],
        logout_uri="https://x/logout",
    )
    _link_current_session(db_session, oauth_client)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    location = resp.json()["redirect_to"]
    assert location.startswith("https://x/logout?next=")
    assert "login" in location


def test_portal_logout_without_clients_returns_null_redirect(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["redirect_to"] is None


def test_portal_logout_dispatches_backchannel_for_linked_clients(
    client, db_session, captured_email, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    _link_current_session(db_session, oauth_client)
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.auth.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0][0].client_id == "cli_bc"
    assert resp.json()["redirect_to"] is None


def test_portal_logout_dispatches_backchannel_across_sessions(
    client, db_session, captured_email, monkeypatch
) -> None:
    """门户登出应登出用户的所有授权：含已结束门户会话上的历史链接。"""
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    stale = SessionModel(
        user_id=user.id,
        token_hash=hash_token(generate_token()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(stale)
    db_session.commit()
    stale.revoked_at = datetime.now(timezone.utc)
    db_session.commit()
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    db_session.add(
        OIDCClientSession(
            session_id=stale.id, client_id=oauth_client.id, user_id=user.id
        )
    )
    db_session.commit()
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.auth.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0][0].sid == str(stale.id)


def test_portal_logout_funnel_includes_clients_with_backchannel(
    client, db_session, captured_email
) -> None:
    """配置了回程地址的网站也要进浏览器串跳，才能清掉当前浏览器会话。"""
    register_and_login(client, captured_email)
    oauth_client = create_client(
        db_session,
        client_id="cli_both",
        redirect_uris=["http://x/cb"],
        logout_uri="https://x/logout",
        backchannel_logout_uri="https://x/backchannel",
    )
    _link_current_session(db_session, oauth_client)
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["redirect_to"].startswith("https://x/logout?next=")


def _link_current_session(db_session, oauth_client: OAuthClient) -> None:
    user = db_session.scalar(select(User))
    portal = db_session.scalar(select(SessionModel))
    db_session.add(
        OIDCClientSession(
            session_id=portal.id,
            client_id=oauth_client.id,
            user_id=user.id,
        )
    )
    db_session.commit()
