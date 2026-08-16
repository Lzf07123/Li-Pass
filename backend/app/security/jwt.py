import base64
import hashlib
import time
import uuid
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.security.crypto import atomic_write_bytes, read_key_bytes_with_retry

# 单文件模式使用的固定 kid；目录模式下 kid 取自文件名。
LEGACY_KID = "lipass-rs256-1"
# 品牌改名前的历史 kid：同密钥签发的旧令牌在过期前仍应可验证，
# JWKS 同时发布两个 kid 指向同一把公钥。
DEPRECATED_KID = "portal-rs256-1"


def _generate_private_key() -> object:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _load_private_key(key_path: Path) -> object:
    last_error: Exception | None = None
    for _ in range(20):
        try:
            return serialization.load_pem_private_key(
                read_key_bytes_with_retry(key_path), password=None
            )
        except (ValueError, TypeError) as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    raise ValueError(f"无法加载 JWT 私钥: {key_path}")


@lru_cache
def _load_key_pair(path: str) -> tuple[object, object]:
    key_path = Path(path)
    if not key_path.exists():
        key = _generate_private_key()
        atomic_write_bytes(
            key_path,
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        )
    private_key = _load_private_key(key_path)
    return private_key, private_key.public_key()


@lru_cache
def _load_key_dir(dir_path: str) -> dict[str, tuple[object, object]]:
    """加载密钥目录中全部 *.pem 私钥，文件名（不含扩展名）即 kid。"""
    directory = Path(dir_path)
    if not directory.is_dir():
        raise ValueError(f"JWT 密钥目录不存在: {dir_path}")
    keys: dict[str, tuple[object, object]] = {}
    for pem_path in sorted(directory.glob("*.pem")):
        private_key = _load_private_key(pem_path)
        keys[pem_path.stem] = (private_key, private_key.public_key())
    if not keys:
        raise ValueError(f"JWT 密钥目录下没有 *.pem 密钥: {dir_path}")
    return keys


def _signing_key(settings) -> tuple[str, object]:
    if settings.jwt_keys_dir:
        keys = _load_key_dir(settings.jwt_keys_dir)
        kid = settings.jwt_active_kid or max(keys)
        if kid not in keys:
            raise ValueError(f"JWT_ACTIVE_KID={kid} 在密钥目录中不存在")
        return kid, keys[kid][0]
    return LEGACY_KID, _load_key_pair(settings.jwt_private_key_path)[0]


def _verification_key(settings, kid: str | None) -> object:
    if settings.jwt_keys_dir:
        keys = _load_key_dir(settings.jwt_keys_dir)
        if kid is None or kid not in keys:
            raise jwt.InvalidKeyError(f"未知 kid: {kid}")
        return keys[kid][1]
    if kid not in (LEGACY_KID, DEPRECATED_KID):
        raise jwt.InvalidKeyError(f"未知 kid: {kid}")
    return _load_key_pair(settings.jwt_private_key_path)[1]


def _b64(number: int) -> str:
    size = max(1, (number.bit_length() + 7) // 8)
    return base64.urlsafe_b64encode(number.to_bytes(size, "big")).rstrip(b"=").decode()


def compute_at_hash(access_token: str) -> str:
    """OIDC Core §3.3.2.11：token 端点同时返回 access_token 与 id_token 时，
    id_token 必须携带 at_hash = base64url(SHA256(access_token) 左 16 字节)。"""
    digest = hashlib.sha256(access_token.encode()).digest()[:16]
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    settings = get_settings()
    kid, private_key = _signing_key(settings)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


def userinfo_audience(settings) -> str:
    """access token 的 aud：本 IdP 的 userinfo 端点（RFC 9068 资源服务器标识）。"""
    return f"{settings.jwt_issuer.rstrip('/')}/oauth2/userinfo"


def absolute_avatar_url(settings, avatar_url: str | None) -> str | None:
    """把头像相对路径拼成绝对 URL，用于 userinfo/id_token 的 picture claim。"""
    if not avatar_url:
        return None
    if avatar_url.startswith(("http://", "https://")):
        return avatar_url
    return f"{settings.jwt_issuer.rstrip('/')}{avatar_url}"


def create_access_token(user, client_id: str, scope: str) -> str:
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.jwt_issuer,
        "sub": str(user.id),
        # access token 只面向 userinfo 端点；id_token 的 aud 才指向 client_id。
        "aud": userinfo_audience(settings),
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
    acr: str = "urn:lipass:acr:1fa",
    sid: str | None = None,
    at_hash: str | None = None,
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
        "acr": acr,
        "scope": scope,
    }
    if nonce:
        payload["nonce"] = nonce
    if at_hash:
        payload["at_hash"] = at_hash
    if sid:
        payload["sid"] = sid
    # 按授权 scope 裁剪 claims（与 userinfo 保持一致）。
    if "email" in scopes:
        payload["email"] = user.email
        payload["email_verified"] = user.email_verified_at is not None
    if "profile" in scopes:
        payload["nickname"] = user.nickname
        payload["name"] = user.nickname
        picture = absolute_avatar_url(settings, getattr(user, "avatar_url", None))
        if picture:
            payload["picture"] = picture
    return _encode(payload)


def issue_logout_token(sub: str, sid: str, client_id: str) -> str:
    """签发 OIDC Back-Channel Logout 登出令牌。

    aud 必须等于目标 client_id；exp 使用短新鲜窗口；jti 供接收方做重放
    防护（OP 侧不落库，由 RP 维护已见 jti 缓存）。
    """
    settings = get_settings()
    now = _now()
    payload = {
        "iss": settings.jwt_issuer,
        "aud": client_id,
        "sub": sub,
        "sid": sid,
        "iat": now,
        "exp": now + timedelta(seconds=settings.logout_token_ttl_seconds),
        "jti": str(uuid.uuid4()),
        "events": {"http://schemas.openid.net/event/backchannel-logout": {}},
    }
    return _encode(payload)


def decode_token(token: str, audience: str | None = None) -> dict:
    settings = get_settings()
    kid = jwt.get_unverified_header(token).get("kid")
    public_key = _verification_key(settings, kid)
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
    if settings.jwt_keys_dir:
        keys = _load_key_dir(settings.jwt_keys_dir)
        return {"keys": [_jwk(kid, public_key) for kid, (_, public_key) in sorted(keys.items())]}
    _, public_key = _load_key_pair(settings.jwt_private_key_path)
    return {
        "keys": [
            _jwk(LEGACY_KID, public_key),
            _jwk(DEPRECATED_KID, public_key),
        ]
    }


def _jwk(kid: str, public_key) -> dict:
    numbers = public_key.public_numbers()
    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64(numbers.n),
        "e": _b64(numbers.e),
    }
