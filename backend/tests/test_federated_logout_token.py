from types import SimpleNamespace

import jwt as pyjwt
import pytest

from app.security.jwt import decode_token, issue_logout_token
from app.services.federated_logout import assert_safe_backchannel_url


def test_logout_token_claims() -> None:
    token = issue_logout_token("sub-1", "sid-1", "cli_a")
    claims = decode_token(token, audience="cli_a")
    assert claims["sub"] == "sub-1"
    assert claims["sid"] == "sid-1"
    assert "http://schemas.openid.net/event/backchannel-logout" in claims["events"]
    assert claims["jti"]


def test_logout_token_expires_within_configured_window() -> None:
    token = issue_logout_token("sub-1", "sid-1", "cli_a")
    claims = pyjwt.decode(token, options={"verify_signature": False})
    assert 0 < claims["exp"] - claims["iat"] <= 600


def test_safe_url_rejects_loopback_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    with pytest.raises(ValueError):
        assert_safe_backchannel_url("https://127.0.0.1/logout")


def test_safe_url_rejects_http_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    with pytest.raises(ValueError):
        assert_safe_backchannel_url("http://93.184.216.34/logout")


def test_safe_url_allows_public_https_in_production(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings",
        lambda: SimpleNamespace(environment="production"),
    )
    assert_safe_backchannel_url("https://93.184.216.34/logout")


def test_safe_url_allows_localhost_in_development() -> None:
    assert_safe_backchannel_url("http://localhost:3001/backchannel-logout")
