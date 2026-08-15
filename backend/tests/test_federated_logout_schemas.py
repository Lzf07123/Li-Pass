import pytest
from pydantic import ValidationError

from app.schemas.oauth import ClientCreate, ClientUpdate


def test_client_create_accepts_logout_fields() -> None:
    payload = ClientCreate(
        name="X",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/"],
        backchannel_logout_uri="https://x/backchannel",
    )
    assert payload.post_logout_redirect_uris == ["https://x/"]
    assert payload.backchannel_logout_uri == "https://x/backchannel"


def test_post_logout_redirect_uris_rejects_javascript() -> None:
    with pytest.raises(ValidationError):
        ClientCreate(
            name="X",
            redirect_uris=["http://x/cb"],
            post_logout_redirect_uris=["javascript:alert(1)"],
        )


def test_post_logout_redirect_uris_rejects_duplicates() -> None:
    with pytest.raises(ValidationError):
        ClientCreate(
            name="X",
            redirect_uris=["http://x/cb"],
            post_logout_redirect_uris=["https://x/", "https://x/"],
        )


def test_backchannel_uri_rejects_credentials() -> None:
    with pytest.raises(ValidationError):
        ClientCreate(
            name="X",
            redirect_uris=["http://x/cb"],
            backchannel_logout_uri="https://user:pass@x/backchannel",
        )


def test_client_update_partial() -> None:
    payload = ClientUpdate(post_logout_redirect_uris=[])
    assert payload.model_dump(exclude_unset=True) == {"post_logout_redirect_uris": []}
