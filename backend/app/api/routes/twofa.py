import pyotp
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.schemas.auth import PasswordConfirm, TwoFaTotpEnable
from app.security.passwords import verify_password
from app.services.audit import log_audit
from app.services.twofa import (
    build_otpauth_uri,
    enable_totp,
    generate_recovery_codes,
    qr_data_url,
)

router = APIRouter(prefix="/api/v1/me/2fa", tags=["twofa"])


def _require_password(password: str, user: User) -> None:
    if not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")


@router.get("/status")
def twofa_status(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    remaining = db.scalar(
        select(func.count()).select_from(RecoveryCode).where(
            RecoveryCode.user_id == user.id, RecoveryCode.used_at.is_(None)
        )
    )
    return {
        "email_otp_enabled": user.email_otp_enabled,
        "totp_enabled": user.totp_secret_encrypted is not None,
        "recovery_codes_remaining": remaining or 0,
    }


@router.post("/email/enable")
def enable_email_otp(
    payload: PasswordConfirm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # 2FA 开启/关闭/更换均属于高敏感操作，统一要求当前密码，
    # 防止会话被临时窃取后静默改动认证策略。
    _require_password(payload.current_password, user)
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先验证邮箱")
    user.email_otp_enabled = True
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_email_enable")
    return {"message": "邮箱二次验证已开启"}


@router.post("/email/disable")
def disable_email_otp(
    payload: PasswordConfirm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_password(payload.current_password, user)
    user.email_otp_enabled = False
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_email_disable")
    return {"message": "邮箱二次验证已关闭"}


@router.get("/totp/setup")
def totp_setup(user: User = Depends(get_current_user)) -> dict:
    if user.totp_secret_encrypted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "TOTP 已开启")
    secret = pyotp.random_base32()
    uri = build_otpauth_uri(secret, user.email)
    return {"secret": secret, "otpauth_uri": uri, "qr_data_url": qr_data_url(uri)}


@router.post("/totp/enable")
def totp_enable(
    payload: TwoFaTotpEnable,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # 开启 TOTP 属于高敏感操作，要求当前密码确认，防止会话被临时窃取后直接接管账号。
    _require_password(payload.current_password, user)
    if not pyotp.TOTP(payload.secret).verify(payload.code, valid_window=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效")
    enable_totp(user, payload.secret, db)
    codes = generate_recovery_codes(db, user)
    log_audit(db, "user", str(user.id), "2fa_totp_enable")
    return {"message": "TOTP 已开启", "recovery_codes": codes}


@router.post("/totp/disable")
def totp_disable(
    payload: PasswordConfirm,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_password(payload.current_password, user)
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    codes = db.scalars(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ).all()
    for code in codes:
        db.delete(code)
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_totp_disable")
    return {"message": "TOTP 已关闭"}
