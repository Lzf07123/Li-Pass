import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.otp import OtpPurpose
from app.models.session import Session as SessionModel
from app.models.user import User, UserStatus
from app.schemas.auth import (
    ConfirmPasswordResetRequest,
    EmailVerifyRequest,
    LoginRequest,
    PasswordResetRequest,
    RegisterRequest,
    TwoFaSendRequest,
    TwoFaVerifyRequest,
    UserOut,
    serialize_user,
)
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_token, hash_token
from app.services.email import get_email_service
from app.services.otps import create_otp, verify_otp
from app.services.audit import log_audit
from app.services.twofa import (
    consume_recovery_code,
    create_challenge,
    get_twofa_store,
    verify_totp,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


def _create_session_and_cookie(
    db: Session,
    user: User,
    request: Request,
    response: Response,
    auth_method: str,
) -> None:
    now = datetime.now(timezone.utc)
    token = generate_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        auth_method=auth_method,
        device_name=request.headers.get("user-agent", "")[:120],
        ip=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", ""),
        expires_at=now + timedelta(days=settings.session_ttl_days),
        last_used_at=now,
    )
    db.add(session)
    user.last_login_at = now
    user.last_login_ip = request.client.host if request.client else None
    db.commit()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        max_age=settings.session_ttl_days * 86400,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nickname=payload.nickname,
    )
    db.add(user)
    db.commit()

    code = create_otp(db, OtpPurpose.register, email)
    get_email_service().send_verification(email, code)
    return serialize_user(user)


@router.post("/email/verify")
def verify_email(payload: EmailVerifyRequest, db: Session = Depends(get_db)) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    if not verify_otp(db, OtpPurpose.register, email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "邮箱已验证"}


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if user.status != UserStatus.active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "账号已被禁用")

    methods = []
    if user.email_otp_enabled:
        methods.append("email_otp")
    if user.totp_secret_encrypted:
        methods.append("totp")
    if methods:
        methods.append("recovery")
        challenge_id = create_challenge(get_twofa_store(), str(user.id), methods)
        if user.email_otp_enabled:
            code = create_otp(db, OtpPurpose.two_fa, user.email)
            get_email_service().send_verification(user.email, code)
        log_audit(
            db,
            "user",
            str(user.id),
            "login_step1",
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
        return {"requires_2fa": True, "challenge_id": challenge_id, "methods": methods}

    _create_session_and_cookie(db, user, request, response, auth_method="password")
    log_audit(
        db,
        "user",
        str(user.id),
        "login",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return serialize_user(user)


@router.post("/2fa/send")
def send_twofa_code(
    payload: TwoFaSendRequest,
    db: Session = Depends(get_db),
) -> dict:
    challenge = get_twofa_store().get(payload.challenge_id)
    if challenge is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "挑战不存在或已过期")
    if "email_otp" not in challenge.methods:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该账号未开启邮箱验证码")
    user = db.get(User, uuid.UUID(challenge.user_id))
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不可用")
    code = create_otp(db, OtpPurpose.two_fa, user.email)
    get_email_service().send_verification(user.email, code)
    return {"message": "验证码已发送"}


@router.post("/2fa/verify", response_model=UserOut)
def verify_twofa(
    payload: TwoFaVerifyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    store = get_twofa_store()
    challenge = store.get(payload.challenge_id)
    if challenge is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "挑战不存在或已过期")
    if challenge.attempts >= 5:
        store.delete(payload.challenge_id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "尝试次数过多")
    user = db.get(User, uuid.UUID(challenge.user_id))
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号不可用")

    ok = False
    if payload.method == "totp":
        ok = verify_totp(user, payload.code)
    elif payload.method == "email_otp":
        ok = verify_otp(db, OtpPurpose.two_fa, user.email, payload.code)
    elif payload.method == "recovery":
        ok = consume_recovery_code(db, user, payload.code)

    if not ok:
        challenge.attempts += 1
        store.save(payload.challenge_id, challenge)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效")

    store.delete(payload.challenge_id)
    _create_session_and_cookie(db, user, request, response, auth_method=payload.method)
    log_audit(
        db,
        "user",
        str(user.id),
        "2fa_login",
        detail={"method": payload.method},
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return serialize_user(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        session = db.scalar(
            select(SessionModel).where(SessionModel.token_hash == hash_token(token))
        )
        if session is not None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
    response.delete_cookie(settings.session_cookie_name)


@router.post("/password/reset", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest, db: Session = Depends(get_db)
) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        code = create_otp(db, OtpPurpose.reset_password, email)
        get_email_service().send_password_reset(email, code)
    return {"message": "如果该邮箱已注册，重置验证码已发送"}


@router.post("/password/reset/confirm")
def confirm_password_reset(
    payload: ConfirmPasswordResetRequest, db: Session = Depends(get_db)
) -> dict:
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_otp(db, OtpPurpose.reset_password, email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "密码已重置"}
