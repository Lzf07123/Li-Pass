import jwt as pyjwt

from app.core.config import get_settings
from app.security.jwt import (
    create_access_token,
    create_id_token,
    decode_token,
    public_jwks,
)


class FakeUser:
    id = "00000000-0000-0000-0000-000000000001"
    email = "a@example.com"
    nickname = "Alice"
    email_verified_at = None


def test_access_token_roundtrip() -> None:
    token = create_access_token(FakeUser(), "cli_demo", "openid profile email")
    claims = decode_token(token, audience="cli_demo")
    assert claims["sub"] == FakeUser.id
    assert claims["aud"] == "cli_demo"
    assert claims["scope"] == "openid profile email"


def test_access_token_wrong_audience_fails() -> None:
    token = create_access_token(FakeUser(), "cli_demo", "openid")
    try:
        decode_token(token, audience="cli_other")
        raise AssertionError("should have raised")
    except pyjwt.InvalidAudienceError:
        pass


def test_id_token_has_nonce_and_acr() -> None:
    token = create_id_token(FakeUser(), "cli_demo", "nonce-123", "openid")
    claims = decode_token(token, audience="cli_demo")
    assert claims["nonce"] == "nonce-123"
    assert claims["acr"] == "urn:portal-oss:acr:1fa"
    assert claims["email"] == "a@example.com"


def test_jwks_contains_rs256_key() -> None:
    jwks = public_jwks()
    assert jwks["keys"][0]["alg"] == "RS256"
    assert jwks["keys"][0]["kty"] == "RSA"
    assert jwks["keys"][0]["kid"] == "portal-rs256-1"
