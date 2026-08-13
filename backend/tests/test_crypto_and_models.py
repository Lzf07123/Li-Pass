from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.security.crypto import decrypt_str, encrypt_str


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
