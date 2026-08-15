import urllib.parse
from datetime import datetime, timezone

import httpx

from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.jwt import decode_token
from app.services.federated_logout import (
    LogoutTarget,
    collect_logout_targets,
    dispatch_backchannel_logout,
)
from tests.helpers import create_client


def test_dispatch_posts_logout_token_and_retries() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.content.decode())
        if len(seen) < 2:
            return httpx.Response(500)
        return httpx.Response(204)

    result = dispatch_backchannel_logout(
        [
            LogoutTarget(
                uri="https://rp.example/backchannel",
                client_id="cli_a",
                sid="sid-1",
                sub="sub-1",
            )
        ],
        transport=httpx.MockTransport(handler),
    )
    assert result == {"cli_a": True}
    assert len(seen) == 2
    token = dict(urllib.parse.parse_qsl(seen[0]))["logout_token"]
    claims = decode_token(token, audience="cli_a")
    assert claims["sid"] == "sid-1"
    assert claims["sub"] == "sub-1"


def test_dispatch_gives_up_after_configured_retries() -> None:
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(503)

    target = LogoutTarget(
        uri="https://rp.example/backchannel",
        client_id="cli_a",
        sid="sid-1",
        sub="sub-1",
    )
    result = dispatch_backchannel_logout(
        [target], transport=httpx.MockTransport(handler)
    )
    assert result == {"cli_a": False}
    assert len(attempts) == 3


def test_collect_logout_targets_only_backchannel_clients(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    with_bc = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    without_bc = create_client(
        db_session,
        client_id="cli_plain",
        redirect_uris=["http://y/cb"],
        logout_uri="https://y/logout",
    )
    portal = SessionModel(
        user_id=user.id,
        token_hash="hash-1",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(portal)
    db_session.commit()
    for client in (with_bc, without_bc):
        db_session.add(
            OIDCClientSession(
                session_id=portal.id, client_id=client.id, user_id=user.id
            )
        )
    db_session.commit()

    targets = collect_logout_targets(db_session, [portal.id])
    assert [(t.client_id, t.sid, t.sub) for t in targets] == [
        ("cli_bc", str(portal.id), str(user.id))
    ]
