import hashlib
import hmac
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.security.crypto import _fernet, _hmac_key, decrypt_str, encrypt_str
from app.security.tokens import hash_token
from app.services.twofa import consume_recovery_code
from tests.helpers import register_and_login


def test_crypto_roundtrip() -> None:
    encrypted = encrypt_str("top-secret")
    assert encrypted != "top-secret"
    assert decrypt_str(encrypted) == "top-secret"


def test_twofa_models(db_session) -> None:
    user = User(
        email="a@example.com",
        password_hash="x",
        nickname="A",
        totp_secret_encrypted=encrypt_str("SECRET"),
        email_otp_enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.totp_secret_encrypted is not None

    code = RecoveryCode(user_id=user.id, code_hash="h")
    log = AuditLog(actor_type="user", actor_id=str(user.id), action="login")
    db_session.add_all([code, log])
    db_session.commit()
    assert code.id is not None
    assert log.id is not None


def test_consume_recovery_code_rejects_legacy_sha256_hash(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(
        RecoveryCode(user_id=user.id, code_hash=hash_token("legacy-code-00000001"))
    )
    db_session.commit()
    assert consume_recovery_code(db_session, user, "legacy-code-00000001") is False


def test_hmac_key_is_domain_separated_from_encryption_key() -> None:
    path = get_settings().encryption_key_path
    _fernet(path)  # 确保密钥文件存在
    raw = Path(path).read_bytes()
    expected = hmac.new(raw, b"lipass:hmac:v2", hashlib.sha256).digest()
    assert _hmac_key(path) == expected
    assert _hmac_key(path) != raw
