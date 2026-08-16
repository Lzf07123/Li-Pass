import base64
import io
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pyotp
import qrcode
import qrcode.image.svg
from cryptography.fernet import InvalidToken
from sqlalchemy import select

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models.recovery_code import RecoveryCode
from app.security.crypto import decrypt_str, encrypt_str, hmac_hex


@dataclass
class TwoFaChallenge:
    user_id: str
    methods: list[str]
    remember_me: bool = False
    attempts: int = 0
    expires_at: str = ""


class TwoFactorChallengeStore:
    def create(self, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> str:
        raise NotImplementedError

    def get(self, challenge_id: str) -> TwoFaChallenge | None:
        raise NotImplementedError

    def save(self, challenge_id: str, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> None:
        raise NotImplementedError

    def delete(self, challenge_id: str) -> None:
        raise NotImplementedError


class InMemoryTwoFactorChallengeStore(TwoFactorChallengeStore):
    def __init__(self) -> None:
        self._items: dict[str, tuple[TwoFaChallenge, datetime]] = {}

    def create(self, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> str:
        self._prune()
        challenge_id = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        challenge.expires_at = expires.isoformat()
        self._items[challenge_id] = (challenge, expires)
        return challenge_id

    def _prune(self) -> None:
        if len(self._items) < 1000:
            return
        now = datetime.now(timezone.utc)
        expired = [k for k, (_, exp) in self._items.items() if exp < now]
        for key in expired:
            self._items.pop(key, None)

    def get(self, challenge_id: str) -> TwoFaChallenge | None:
        item = self._items.get(challenge_id)
        if item is None:
            return None
        challenge, expires = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(challenge_id, None)
            return None
        return challenge

    def save(self, challenge_id: str, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        challenge.expires_at = expires.isoformat()
        self._items[challenge_id] = (challenge, expires)

    def delete(self, challenge_id: str) -> None:
        self._items.pop(challenge_id, None)


class RedisTwoFactorChallengeStore(TwoFactorChallengeStore):
    def __init__(self, client) -> None:
        self._client = client

    def _key(self, challenge_id: str) -> str:
        return f"twofa:{challenge_id}"

    def create(self, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> str:
        challenge_id = secrets.token_urlsafe(24)
        challenge.expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).isoformat()
        self._client.setex(
            self._key(challenge_id), ttl_seconds, json.dumps(challenge.__dict__)
        )
        return challenge_id

    def get(self, challenge_id: str) -> TwoFaChallenge | None:
        raw = self._client.get(self._key(challenge_id))
        return TwoFaChallenge(**json.loads(raw)) if raw else None

    def save(self, challenge_id: str, challenge: TwoFaChallenge, ttl_seconds: int = 600) -> None:
        challenge.expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).isoformat()
        self._client.setex(
            self._key(challenge_id), ttl_seconds, json.dumps(challenge.__dict__)
        )

    def delete(self, challenge_id: str) -> None:
        self._client.delete(self._key(challenge_id))


_memory_store = InMemoryTwoFactorChallengeStore()
_redis_store = None


def get_twofa_store():
    settings = get_settings()
    if settings.twofa_store == "memory":
        return _memory_store
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisTwoFactorChallengeStore(get_redis_client())
    return _redis_store


def create_challenge(
    store, user_id: str, methods: list[str], remember_me: bool = False
) -> str:
    return store.create(
        TwoFaChallenge(user_id=user_id, methods=methods, remember_me=remember_me)
    )


def build_otpauth_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name="Li&Pass")


def qr_data_url(uri: str) -> str:
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buf = io.BytesIO()
    img.save(buf)
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/svg+xml;base64,{encoded}"


def verify_totp(user, code: str) -> bool:
    if not user.totp_secret_encrypted:
        return False
    try:
        secret = decrypt_str(user.totp_secret_encrypted)
        return pyotp.TOTP(secret).verify(code, valid_window=1)
    except (ValueError, TypeError, InvalidToken):
        # 存量/损坏的密钥或非法 Base32 视为验证失败，避免 500
        return False


def enable_totp(user, secret: str, db) -> None:
    user.totp_secret_encrypted = encrypt_str(secret)
    user.totp_enabled_at = datetime.now(timezone.utc)
    db.commit()


def generate_recovery_codes(db, user) -> list[str]:
    # 128 bit 熵，并以 HMAC(服务端密钥) 存储，数据库泄露后无法离线爆破。
    codes = [secrets.token_hex(16) for _ in range(10)]
    for code in codes:
        db.add(RecoveryCode(user_id=user.id, code_hash=hmac_hex(code)))
    db.commit()
    return codes


def consume_recovery_code(db, user, code: str) -> bool:
    code_hash = hmac_hex(code)
    record = db.scalar(
        select(RecoveryCode).where(
            RecoveryCode.user_id == user.id,
            RecoveryCode.code_hash == code_hash,
            RecoveryCode.used_at.is_(None),
        )
    )
    if record is None:
        return False
    record.used_at = datetime.now(timezone.utc)
    db.commit()
    return True
