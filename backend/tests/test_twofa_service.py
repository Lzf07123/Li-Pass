import pyotp

from app.models.user import User
from app.services.twofa import (
    build_otpauth_uri,
    consume_recovery_code,
    enable_totp,
    generate_recovery_codes,
    qr_data_url,
    verify_totp,
)


def test_recovery_codes_roundtrip(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    codes = generate_recovery_codes(db_session, user)
    assert len(codes) == 10
    assert consume_recovery_code(db_session, user, codes[0]) is True
    assert consume_recovery_code(db_session, user, codes[0]) is False
    assert consume_recovery_code(db_session, user, codes[1]) is True


def test_totp_enable_and_verify(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    secret = pyotp.random_base32()
    enable_totp(user, secret, db_session)
    totp = pyotp.TOTP(secret)
    assert verify_totp(user, totp.now()) is True
    assert verify_totp(user, "000000") is False


def test_otpauth_uri_and_qr(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    uri = build_otpauth_uri("SECRET", user.email)
    assert uri.startswith("otpauth://totp/")
    assert qr_data_url(uri).startswith("data:image/svg+xml;base64,")
