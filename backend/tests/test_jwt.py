from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import jwt as pyjwt

from app.core.config import get_settings
from app.security.jwt import (
    absolute_avatar_url,
    create_access_token,
    create_id_token,
    decode_token,
    public_jwks,
    userinfo_audience,
)


class FakeUser:
    id = "00000000-0000-0000-0000-000000000001"
    email = "a@example.com"
    nickname = "Alice"
    email_verified_at = None
    avatar_url = "/uploads/avatars/00000000-0000-0000-0000-000000000001/a.jpg"


def test_access_token_roundtrip() -> None:
    token = create_access_token(FakeUser(), "cli_demo", "openid profile email")
    audience = userinfo_audience(get_settings())
    claims = decode_token(token, audience=audience)
    assert claims["sub"] == FakeUser.id
    assert claims["aud"] == "http://localhost:8000/oauth2/userinfo"
    assert claims["scope"] == "openid profile email"
    assert claims["client_id"] == "cli_demo"


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
    assert claims["acr"] == "urn:lipass:acr:1fa"
    # 仅授权 openid 时不应泄露 email/nickname。
    assert "email" not in claims
    assert "nickname" not in claims
    assert "picture" not in claims


def test_id_token_claims_follow_scope() -> None:
    token = create_id_token(FakeUser(), "cli_demo", "nonce-123", "openid profile email")
    claims = decode_token(token, audience="cli_demo")
    assert claims["email"] == "a@example.com"
    assert claims["email_verified"] is False
    assert claims["nickname"] == "Alice"
    assert claims["picture"] == (
        "http://localhost:8000/uploads/avatars/"
        "00000000-0000-0000-0000-000000000001/a.jpg"
    )


def test_jwks_contains_rs256_key() -> None:
    jwks = public_jwks()
    assert {key["kid"] for key in jwks["keys"]} == {
        "lipass-rs256-1",
        "portal-rs256-1",
    }
    assert all(key["alg"] == "RS256" for key in jwks["keys"])
    assert all(key["kty"] == "RSA" for key in jwks["keys"])


def test_legacy_kid_token_still_verifies() -> None:
    """单文件模式下，历史 kid=portal-rs256-1 的令牌（同密钥签名）仍可验证。"""
    from app.security import jwt as jwt_module

    settings = get_settings()
    kid, private_key = jwt_module._signing_key(settings)
    assert kid == "lipass-rs256-1"
    now = datetime.now(timezone.utc)
    legacy_token = pyjwt.encode(
        {
            "iss": settings.jwt_issuer,
            "sub": FakeUser.id,
            "aud": userinfo_audience(settings),
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "portal-rs256-1"},
    )
    claims = decode_token(legacy_token, audience=userinfo_audience(settings))
    assert claims["sub"] == FakeUser.id


def test_absolute_avatar_url_handles_relative_and_external() -> None:
    settings = get_settings()
    assert absolute_avatar_url(settings, None) is None
    assert absolute_avatar_url(settings, "/uploads/avatars/a.jpg") == (
        "http://localhost:8000/uploads/avatars/a.jpg"
    )
    external = "https://cdn.example.com/a.jpg"
    assert absolute_avatar_url(settings, external) == external


def test_jwt_multi_kid_rotation(tmp_path, monkeypatch) -> None:
    from app.core.config import Settings
    from app.security import jwt as jwt_module

    keys_dir = tmp_path / "jwt"
    keys_dir.mkdir()
    _write_test_key(keys_dir / "lipass-rs256-1.pem")
    _write_test_key(keys_dir / "lipass-rs256-2.pem")
    settings = Settings(
        _env_file=None,
        jwt_keys_dir=str(keys_dir),
        jwt_active_kid="lipass-rs256-2",
    )
    monkeypatch.setattr(jwt_module, "get_settings", lambda: settings)
    jwt_module._load_key_dir.cache_clear()

    jwks = public_jwks()
    assert {key["kid"] for key in jwks["keys"]} == {
        "lipass-rs256-1",
        "lipass-rs256-2",
    }

    token = create_access_token(FakeUser(), "cli_demo", "openid")
    assert pyjwt.get_unverified_header(token)["kid"] == "lipass-rs256-2"
    claims = decode_token(token, audience=userinfo_audience(settings))
    assert claims["sub"] == FakeUser.id

    # 用目录内旧 kid 签发的 token 在轮换后仍应可验证（JWKS 同时发布全部公钥）。
    old_settings = Settings(
        _env_file=None,
        jwt_keys_dir=str(keys_dir),
        jwt_active_kid="lipass-rs256-1",
    )
    monkeypatch.setattr(jwt_module, "get_settings", lambda: old_settings)
    old_token = create_access_token(FakeUser(), "cli_demo", "openid")
    monkeypatch.setattr(jwt_module, "get_settings", lambda: settings)
    assert decode_token(old_token, audience=userinfo_audience(settings))["sub"] == (
        FakeUser.id
    )

    # 目录中不存在的 kid 必须被拒绝（即使签名本身有效）。
    from cryptography.hazmat.primitives.asymmetric import rsa

    rogue_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = pyjwt.encode(
        {
            "iss": settings.jwt_issuer,
            "sub": FakeUser.id,
            "aud": userinfo_audience(settings),
            "iat": datetime.now(timezone.utc),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        },
        rogue_key,
        algorithm="RS256",
        headers={"kid": "lipass-rs256-9"},
    )
    with pytest.raises(pyjwt.InvalidKeyError):
        decode_token(forged, audience=userinfo_audience(settings))


def _write_test_key(path: Path):
    from app.security.crypto import atomic_write_bytes
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    atomic_write_bytes(
        path,
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
    )
    return key


def test_rotate_script_next_kid(tmp_path) -> None:
    from scripts.rotate_jwt_key import next_kid

    (tmp_path / "lipass-rs256-1.pem").write_text("x")
    (tmp_path / "lipass-rs256-3.pem").write_text("x")
    (tmp_path / "portal-rs256-2.pem").write_text("x")
    (tmp_path / "notes.txt").write_text("ignore me")
    assert next_kid(tmp_path) == "lipass-rs256-4"
