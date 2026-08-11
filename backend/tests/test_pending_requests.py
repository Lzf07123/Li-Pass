from app.services.pending_requests import (
    InMemoryPendingRequestStore,
    PendingAuthRequest,
)


def make_request() -> PendingAuthRequest:
    return PendingAuthRequest(
        client_id="cli_demo",
        redirect_uri="http://localhost:3001/callback",
        scope="openid profile",
        state="state-1",
        nonce="nonce-1",
        code_challenge="challenge",
        code_challenge_method="S256",
    )


def test_inmemory_create_get_delete() -> None:
    store = InMemoryPendingRequestStore()
    request_id = store.create(make_request())
    assert store.get(request_id) == make_request()
    store.delete(request_id)
    assert store.get(request_id) is None


def test_inmemory_expired_request_returns_none() -> None:
    from datetime import datetime, timedelta, timezone

    store = InMemoryPendingRequestStore()
    request_id = store.create(make_request())
    item = store._items[request_id]
    store._items[request_id] = (
        item[0],
        datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert store.get(request_id) is None
