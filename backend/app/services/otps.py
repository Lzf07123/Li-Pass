import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.otp import Otp, OtpPurpose
from app.security.tokens import generate_otp_code, hash_otp_code

MAX_ATTEMPTS = 5
OTP_TTL_MINUTES = 10


def _as_utc(dt: datetime) -> datetime:
    """Normalize a possibly naive datetime to UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_otp(
    db: Session, purpose: OtpPurpose, target: str, ttl_minutes: int = OTP_TTL_MINUTES
) -> str:
    code = generate_otp_code()
    db.add(
        Otp(
            purpose=purpose,
            target=target.lower(),
            code_hash=hash_otp_code(code),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return code


def verify_otp(db: Session, purpose: OtpPurpose, target: str, code: str) -> bool:
    otp = db.scalar(
        select(Otp)
        .where(Otp.purpose == purpose, Otp.target == target.lower(), Otp.consumed_at.is_(None))
        .order_by(Otp.created_at.desc())
    )
    if otp is None:
        return False
    if otp.attempts >= MAX_ATTEMPTS or _as_utc(otp.expires_at) < datetime.now(timezone.utc):
        return False
    if secrets.compare_digest(hash_otp_code(code), otp.code_hash):
        otp.consumed_at = datetime.now(timezone.utc)
        otp.attempts += 1
        db.commit()
        return True
    otp.attempts += 1
    db.commit()
    return False
