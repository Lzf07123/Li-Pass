from app.services.logout_requests import (
    InMemoryLogoutRequestStore,
    PendingLogoutRequest,
)


def _pending() -> PendingLogoutRequest:
    return PendingLogoutRequest(
        client_id="cli_a",
        post_logout_redirect_uri="https://x/after",
        state="st-1",
        sid="sid-1",
        sub="sub-1",
        client_name="Demo",
    )


def test_store_roundtrip() -> None:
    store = InMemoryLogoutRequestStore()
    request_id = store.create(_pending())
    loaded = store.get(request_id)
    assert loaded is not None
    assert loaded.client_name == "Demo"
    assert loaded.state == "st-1"
    store.delete(request_id)
    assert store.get(request_id) is None


def test_store_returns_none_for_unknown_id() -> None:
    store = InMemoryLogoutRequestStore()
    assert store.get("missing") is None
