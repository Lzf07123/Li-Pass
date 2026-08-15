"""敏感操作 step-up 复核：统一密码复核、限流、审计与 30 分钟免复核窗口。

安全边界（详见 docs/superpowers/specs/2026-08-16-sensitive-stepup-window-design.md）：

- 窗口按会话存储（sessions.stepup_at），一台设备复核不豁免其它设备；
- 登录成功不写入 stepup_at，窗口只能由已登录会话上的显式密码复核获得；
- 固定窗口（自复核时刻起 STEPUP_WINDOW_MINUTES 分钟，不滑动）；
- 复核失败按 email+IP 与全局 email 双层限流并记审计。
"""

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.otp import OtpPurpose
from app.models.session import Session as SessionModel
from app.models.user import User
from app.security.passwords import verify_password
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.otps import verify_otp
from app.services.rate_limit import get_rate_limiter
from app.services.twofa import verify_totp

STEPUP_REQUIRED_DETAIL = "需要重新验证密码"
WRONG_PASSWORD_DETAIL = "当前密码错误"
MISSING_STEPUP_2FA_DETAIL = "请选择一种二次验证方式并输入验证码"
INVALID_STEPUP_2FA_DETAIL = "二次验证码无效"


def _as_utc(dt: datetime) -> datetime:
    """把可能为 naive 的时间戳归一化为 UTC（SQLite 读取不带时区信息）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def stepup_status(session: SessionModel) -> dict:
    """当前会话的 step-up 窗口状态，供前端决定是否弹出密码复核框。"""
    settings = get_settings()
    base = {
        "active": False,
        "window_minutes": settings.stepup_window_minutes,
        "expires_in_seconds": 0,
    }
    if settings.stepup_window_minutes <= 0 or session.stepup_at is None:
        return base
    expires_at = _as_utc(session.stepup_at) + timedelta(
        minutes=settings.stepup_window_minutes
    )
    remaining = int((expires_at - _now()).total_seconds())
    if remaining <= 0:
        return base
    return {
        "active": True,
        "window_minutes": settings.stepup_window_minutes,
        "expires_in_seconds": remaining,
    }


def authorize_stepup(
    request: Request,
    db: Session,
    user: User,
    session: SessionModel,
    password: str | None,
) -> None:
    """授权敏感操作：提供密码则验证并开窗；未提供则要求窗口内。

    - 密码非空且正确：写入 stepup_at、清零限流、审计 stepup_verify_success；
    - 密码非空且错误：限流 + 审计 stepup_failed，返回 400；
    - 密码为空且窗口内：放行；
    - 密码为空且窗口外：审计 stepup_required，返回 403。
    """
    settings = get_settings()
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent")
    provided = password is not None and password != ""
    if not provided:
        if stepup_status(session)["active"]:
            return
        log_audit(
            db,
            "user",
            str(user.id),
            "stepup_required",
            category="security",
            ip=ip,
            user_agent=user_agent,
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, STEPUP_REQUIRED_DETAIL)

    email_key = user.email
    email_count = get_rate_limiter().hit(
        "stepup_email",
        email_key,
        settings.stepup_email_rate_window_seconds,
    )
    if email_count > settings.stepup_email_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "stepup",
            email_count,
            settings.stepup_email_rate_limit,
            actor_type="user",
            actor_id=str(user.id),
            ip=ip,
            user_agent=user_agent,
            detail={"action": "stepup", "reason": "email_rate_limit"},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试"
        )

    pair_key = f"{user.email}:{ip}"
    if not verify_password(password, user.password_hash):
        count = get_rate_limiter().hit(
            "stepup", pair_key, settings.stepup_rate_window_seconds
        )
        log_audit(
            db,
            "user",
            str(user.id),
            "stepup_failed",
            category="security",
            ip=ip,
            user_agent=user_agent,
        )
        if count > settings.stepup_rate_limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试"
            )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, WRONG_PASSWORD_DETAIL)

    get_rate_limiter().reset("stepup", pair_key)
    get_rate_limiter().reset("stepup_email", email_key)
    session.stepup_at = _now()
    db.commit()
    log_audit(
        db,
        "user",
        str(user.id),
        "stepup_verify_success",
        category="security",
        ip=ip,
        user_agent=user_agent,
        detail={"window_minutes": settings.stepup_window_minutes},
    )


def verify_stepup_2fa(
    db: Session, user: User, method: str, code: str
) -> bool:
    """复核注销/删除等关键操作时的「任意 2FA」验证码。"""
    if method == "email_otp":
        # 邮箱验证码自带每码 5 次尝试锁与 10 分钟有效期。
        return verify_otp(db, OtpPurpose.two_fa, user.email, code)
    if method == "totp":
        return verify_totp(user, code)
    return False


def authorize_critical_operation(
    request: Request,
    db: Session,
    user: User,
    session: SessionModel,
    password: str | None,
    stepup_method: str | None,
    stepup_code: str | None,
    missing_password_detail: str,
) -> None:
    """注销/删除账号等高危操作：必须当场「密码 + 任意 2FA」，窗口不豁免。"""
    settings = get_settings()
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent")
    if not password:
        log_audit(
            db,
            "user",
            str(user.id),
            "stepup_required",
            category="security",
            ip=ip,
            user_agent=user_agent,
            detail={"reason": "critical_operation"},
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, missing_password_detail)

    # 密码复核复用现有逻辑（限流 + 审计 + 开窗），
    # 之后必须再用任意一种 2FA 完成二次验证。
    authorize_stepup(request, db, user, session, password)
    if stepup_method not in ("email_otp", "totp") or not stepup_code:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, MISSING_STEPUP_2FA_DETAIL
        )

    otp_key = f"{user.email}:{stepup_method}"
    if not verify_stepup_2fa(db, user, stepup_method, stepup_code):
        count = get_rate_limiter().hit(
            "stepup_2fa", otp_key, settings.stepup_rate_window_seconds
        )
        log_audit(
            db,
            "user",
            str(user.id),
            "stepup_2fa_failed",
            category="security",
            ip=ip,
            user_agent=user_agent,
            detail={"method": stepup_method},
        )
        if count > settings.stepup_rate_limit:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS, "尝试次数过多，请稍后再试"
            )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, INVALID_STEPUP_2FA_DETAIL
        )
    get_rate_limiter().reset("stepup_2fa", otp_key)
