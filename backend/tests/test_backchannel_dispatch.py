import urllib.parse
from datetime import datetime, timezone

import httpx
import httpcore
import pytest

from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.jwt import decode_token
from app.services.federated_logout import (
    _PinnedDNSBackend,
    _validate_public_addresses,
    LogoutTarget,
    collect_logout_targets,
    dispatch_backchannel_logout,
    resolve_safe_backchannel_target,
)
from tests.helpers import create_client


def test_validate_public_addresses_rejects_ipv4_mapped_ipv6() -> None:
    for bad in (
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
    ):
        with pytest.raises(ValueError):
            _validate_public_addresses({bad})
    assert _validate_public_addresses({"8.8.8.8"}) == ["8.8.8.8"]


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


def test_pinned_backend_dials_resolved_ip(monkeypatch) -> None:
    calls: list[tuple[str, int]] = []

    def fake_connect(self, host, port, timeout=None, local_address=None, socket_options=None):
        calls.append((host, port))
        raise httpcore.ConnectError("no route")

    monkeypatch.setattr(httpcore.SyncBackend, "connect_tcp", fake_connect)
    backend = _PinnedDNSBackend({"rp.example": ["192.0.2.1"]})
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("rp.example", 443)
    assert calls == [("192.0.2.1", 443)]


def test_resolve_safe_target_pins_public_addresses(monkeypatch) -> None:
    from types import SimpleNamespace

    monkeypatch.setattr(
        "app.services.federated_logout.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    monkeypatch.setattr(
        "app.services.federated_logout.socket.getaddrinfo",
        lambda host, port: [(2, 1, 6, "", ("93.184.216.34", 0))],
    )
    host, port, pinned = resolve_safe_backchannel_target(
        "https://rp.example/backchannel"
    )
    assert host == "rp.example"
    assert port == 443
    assert pinned == ["93.184.216.34"]
