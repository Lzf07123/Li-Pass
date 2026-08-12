import base64
import time
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.security.crypto import atomic_write_bytes, read_key_bytes_with_retry

KID = "portal-rs256-1"


@lru_cache
def _load_key_pair(path: str) -> tuple[object, object]:
    key_path = Path(path)
    if not key_path.exists():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        atomic_write_bytes(
            key_path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
    last_error: Exception | None = None
    for _ in range(20):
        try:
            private_key = serialization.load_pem_private_key(
                read_key_bytes_with_retry(key_path), password=None
            )
            return private_key, private_key.public_key()
        except (ValueError, TypeError) as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    raise ValueError(f"无法加载 JWT 私钥: {path}")


def _b64(number: int) -> str:
    size = max(1, (number.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(number.to_bytes(size, "big")).rstrip(b"=").decode()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    settings = get_settings()
    private_key, _ = _load_key_pair(settings.jwt_private_key_path)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})


def create_access_token(user, client_id: str, scope: str) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user.id),
        "aud": client_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.oauth_access_token_ttl_minutes),
        "scope": scope,
        "client_id": client_id,
    }
    return _encode(payload)


def create_id_token(
    user,
    client_id: str,
    nonce: str | None,
    scope: str,
    acr: str = "urn:portal-oss:acr:1fa",
) -> str:
    settings = get_settings()
    now = _now()
    scopes = set(scope.split())
    payload: dict = {
        "iss": settings.jwt_issuer,
        "sub": str(user.id),
        "aud": client_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.oauth_id_token_ttl_minutes),
        "nonce": nonce,
        "acr": acr,
        "scope": scope,
    }
    # 按授权 scope 裁剪 claims（与 userinfo 保持一致）。
    if "email" in scopes:
        payload["email"] = user.email
        payload["email_verified"] = user.email_verified_at is not None
    if "profile" in scopes:
        payload["nickname"] = user.nickname
        payload["name"] = user.nickname
    return _encode(payload)


def decode_token(token: str, audience: str | None = None) -> dict:
    settings = get_settings()
    _, public_key = _load_key_pair(settings.jwt_private_key_path)
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=audience,
        issuer=settings.jwt_issuer,
        options={"verify_aud": audience is not None, "verify_iss": True},
    )


def public_jwks() -> dict:
    settings = get_settings()
    _, public_key = _load_key_pair(settings.jwt_private_key_path)
    numbers = public_key.public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "kid": KID,
                "use": "sig",
                "alg": "RS256",
                "n": _b64(numbers.n),
                "e": _b64(numbers.e),
            }
        ]
    }
