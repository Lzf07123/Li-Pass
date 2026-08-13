from datetime import datetime, timedelta, timezone

from app.models.otp import Otp, OtpPurpose
from app.security.tokens import hash_otp_code
from app.services.otps import create_otp, verify_otp


def test_create_and_verify_otp(db_session) -> None:
    code = create_otp(db_session, OtpPurpose.register, "A@Example.com")
    db_session.commit()
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is True
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is False  # 一次性


def test_otp_wrong_code_increments_attempts(db_session) -> None:
    code = create_otp(db_session, OtpPurpose.register, "a@example.com")
    db_session.commit()
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", "000000") is False
    otp = db_session.query(Otp).one()
    assert otp.attempts == 1
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", code) is True


def test_otp_attempts_exhausted_flag(db_session) -> None:
    code = create_otp(db_session, OtpPurpose.register, "a@example.com")
    db_session.commit()
    for _ in range(5):
        assert (
            verify_otp(db_session, OtpPurpose.register, "a@example.com", "000000")
            is False
        )
    from app.services.otps import otp_attempts_exhausted

    assert otp_attempts_exhausted(
        db_session, OtpPurpose.register, "a@example.com"
    ) is True


def test_otp_expired(db_session) -> None:
    otp = Otp(
        purpose=OtpPurpose.register,
        target="a@example.com",
        code_hash=hash_otp_code("123456"),
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    db_session.add(otp)
    db_session.commit()
    assert verify_otp(db_session, OtpPurpose.register, "a@example.com", "123456") is False
