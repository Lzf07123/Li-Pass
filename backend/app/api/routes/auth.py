import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models.account_invite import AccountInvite
from app.models.otp import OtpPurpose
from app.models.session import Session as SessionModel
from app.models.user import User, UserStatus
from app.schemas.auth import (
    ConfirmPasswordResetRequest,
    EmailResendRequest,
    EmailVerifyRequest,
    InviteRegisterRequest,
    LoginRequest,
    PasswordResetRequest,
    RegisterRequest,
    TwoFaSendRequest,
    TwoFaVerifyRequest,
    UserOut,
    serialize_user,
)
from app.security.passwords import (
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.security.tokens import generate_token, hash_token
from app.services.email import get_email_service
from app.services.otps import create_otp, verify_otp
from app.services.audit import log_audit
from app.services.rate_limit import get_rate_limiter
from app.services.twofa import (
    consume_recovery_code,
    create_challenge,
    get_twofa_store,
    verify_totp,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
settings = get_settings()


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


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
        user_agent=request.headers.get("user-agent", "")[:300],
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


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "register", ip, settings.register_rate_window_seconds
        )
        > settings.register_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "注册过于频繁，请稍后再试")
    email = payload.email.lower()
    exists = db.scalar(select(User).where(User.email == email))
    if exists is None:
        user = User(
            email=email,
            password_hash=hash_password(payload.password),
            nickname=payload.nickname,
        )
        db.add(user)
        db.commit()
        code = create_otp(db, OtpPurpose.register, email)
        get_email_service().send_verification(email, code)
    # 无论邮箱是否已注册，统一响应，避免账号枚举；重复注册不重复发信。
    return {"message": "注册请求已受理，验证邮件已发送"}


@router.post("/email/verify")
def verify_email(
    payload: EmailVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "email_verify", ip, settings.email_verify_rate_window_seconds
        )
        > settings.email_verify_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "验证过于频繁，请稍后再试")
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    if not verify_otp(db, OtpPurpose.register, email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")

    user.email_verified_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "邮箱已验证"}


@router.post("/email/verify/resend")
def resend_verify_email(
    payload: EmailResendRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "email_resend", ip, settings.email_verify_rate_window_seconds
        )
        > settings.email_verify_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送过于频繁，请稍后再试")
    email = payload.email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.email_verified_at is None:
        code = create_otp(db, OtpPurpose.register, email)
        get_email_service().send_verification(email, code)
    # 与注册接口一致：已注册且已验证/不存在的邮箱返回相同文案，避免账号枚举。
    return {"message": "如果该邮箱尚未验证，验证邮件已发送"}


@router.post(
    "/invite/register",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
def register_by_invite(
    payload: InviteRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "invite_register", ip, settings.register_rate_window_seconds
        )
        > settings.register_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "注册过于频繁，请稍后再试")

    invite = db.scalar(
        select(AccountInvite).where(
            AccountInvite.token_hash == hash_token(payload.token)
        )
    )
    now = datetime.now(timezone.utc)
    if (
        invite is None
        or invite.used_at is not None
        or _as_utc(invite.expires_at) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邀请链接无效或已过期")
    if db.scalar(select(User).where(User.email == invite.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    # 原子消费邀请：并发请求只有一个能成功把 used_at 置位，
    # 避免同一令牌被两个请求同时通过校验后重复建号或触发唯一约束 500。
    claimed = db.execute(
        update(AccountInvite)
        .where(
            AccountInvite.id == invite.id,
            AccountInvite.used_at.is_(None),
        )
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    if claimed.rowcount != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "邀请链接无效或已过期")

    user = User(
        email=invite.email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        email_verified_at=now,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 与普通注册并发撞邮箱时回滚（邀请消费一并回滚），返回明确的冲突而非 500。
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    log_audit(
        db,
        "user",
        str(user.id),
        "user_register_by_invite",
        target_type="user",
        target_id=str(user.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={"email": invite.email},
    )
    return {"message": "账号已创建，请登录"}


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    # 在 Argon2 之前按 IP 前置限流，防止分布式重试打满 CPU/内存。
    if (
        get_rate_limiter().hit(
            "login_ip", ip, settings.login_rate_window_seconds
        )
        > settings.login_ip_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")
    user_agent = request.headers.get("user-agent")
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        count = get_rate_limiter().hit(
            "login",
            f"{payload.email.lower()}:{ip}",
            settings.login_rate_window_seconds,
        )
        log_audit(
            db,
            "user",
            str(user.id) if user else None,
            "login_failed",
            ip=ip,
            user_agent=user_agent,
        )
        if count > settings.login_rate_limit:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    if password_needs_rehash(user.password_hash):
        # Argon2 参数升级：仅在密码验证通过后重哈希，不向客户端暴露任何信息。
        user.password_hash = hash_password(payload.password)
        db.commit()
    if user.status != UserStatus.active:
        # 与密码错误统一响应，避免泄露账号状态。
        get_rate_limiter().hit(
            "login", f"{user.email}:{ip}", settings.login_rate_window_seconds
        )
        log_audit(
            db,
            "user",
            str(user.id),
            "login_failed",
            detail={"reason": "disabled"},
            ip=ip,
            user_agent=user_agent,
        )
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "邮箱或密码错误")
    get_rate_limiter().reset("login", f"{user.email}:{ip}")

    methods = []
    if user.email_otp_enabled:
        methods.append("email_otp")
    if user.totp_secret_encrypted:
        methods.append("totp")
    if methods:
        methods.append("recovery")
        challenge_id = create_challenge(get_twofa_store(), str(user.id), methods)
        if user.email_otp_enabled:
            send_count = get_rate_limiter().hit(
                "otp_send", user.email, settings.otp_send_window_seconds
            )
            if send_count <= settings.otp_send_limit:
                code = create_otp(db, OtpPurpose.two_fa, user.email)
                get_email_service().send_verification(user.email, code)
        log_audit(
            db,
            "user",
            str(user.id),
            "login_step1",
            ip=ip,
            user_agent=user_agent,
        )
        return {"requires_2fa": True, "challenge_id": challenge_id, "methods": methods}

    _create_session_and_cookie(db, user, request, response, auth_method="password")
    log_audit(
        db,
        "user",
        str(user.id),
        "login",
        ip=ip,
        user_agent=user_agent,
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
    send_count = get_rate_limiter().hit(
        "otp_send", user.email, settings.otp_send_window_seconds
    )
    if send_count > settings.otp_send_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送过于频繁")
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
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "twofa_verify", ip, settings.twofa_verify_rate_window_seconds
        )
        > settings.twofa_verify_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试")
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
    # 删除 Cookie 必须镜像设置时的属性（Secure/SameSite/HttpOnly），
    # 否则 HTTPS 生产环境下浏览器可能不认可这条删除指令，导致登出后 Cookie 仍有效。
    response.delete_cookie(
        settings.session_cookie_name,
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


@router.post("/password/reset", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    email = payload.email.lower()
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "password_reset",
            f"{email}:{ip}",
            settings.password_reset_rate_window_seconds,
        )
        > settings.password_reset_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试")
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
    now = datetime.now(timezone.utc)
    sessions = db.scalars(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.revoked_at.is_(None),
        )
    ).all()
    for session in sessions:
        session.revoked_at = now
    db.commit()
    log_audit(db, "user", str(user.id), "password_reset")
    return {"message": "密码已重置"}
