import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.core.db import get_db
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.schemas.auth import PasswordConfirm, TwoFaTotpEnable
from app.services.audit import log_audit
from app.services.stepup import authorize_stepup
from app.services.twofa import (
    build_otpauth_uri,
    enable_totp,
    generate_recovery_codes,
    qr_data_url,
)

router = APIRouter(prefix="/api/v1/me/2fa", tags=["twofa"])


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
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # 2FA 开启/关闭/更换均属于高敏感操作，统一要求密码复核
    # （或处于该会话 30 分钟 step-up 窗口内），
    # 防止会话被临时窃取后静默改动认证策略。
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    if user.email_verified_at is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请先验证邮箱")
    user.email_otp_enabled = True
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_email_enable", category="2fa")
    return {"message": "邮箱二次验证已开启"}


@router.post("/email/disable")
def disable_email_otp(
    payload: PasswordConfirm,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    if user.totp_secret_encrypted is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "至少保留一种二次验证方式，请先开启 TOTP 认证器",
        )
    user.email_otp_enabled = False
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_email_disable", category="2fa")
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
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # 开启 TOTP 属于高敏感操作，要求密码复核（或 30 分钟窗口内），
    # 防止会话被临时窃取后直接接管账号。
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    try:
        valid_code = pyotp.TOTP(payload.secret).verify(payload.code, valid_window=1)
    except (ValueError, TypeError):
        valid_code = False
    if not valid_code:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效")
    enable_totp(user, payload.secret, db)
    codes = generate_recovery_codes(db, user)
    log_audit(db, "user", str(user.id), "2fa_totp_enable", category="2fa")
    return {"message": "TOTP 已开启", "recovery_codes": codes}


@router.post("/totp/disable")
def totp_disable(
    payload: PasswordConfirm,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    if not user.email_otp_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "至少保留一种二次验证方式，请先开启邮箱验证码",
        )
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    codes = db.scalars(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ).all()
    for code in codes:
        db.delete(code)
    db.commit()
    log_audit(db, "user", str(user.id), "2fa_totp_disable", category="2fa")
    return {"message": "TOTP 已关闭"}
