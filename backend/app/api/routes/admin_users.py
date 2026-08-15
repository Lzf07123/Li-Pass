import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_session
from app.core.config import get_settings
from app.core.db import get_db
from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.schemas.auth import PasswordConfirm
from app.security.passwords import hash_password
from app.security.tokens import generate_token, hash_token
from app.services.account_deletion import delete_user_account
from app.services.admin_stats import invalidate_admin_stats_cache
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.geoip import describe_ip
from app.services.email import get_email_service
from app.services.rate_limit import get_rate_limiter
from app.services.stepup import authorize_stepup

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin)],
)


class AdminUserUpdate(BaseModel):
    status: UserStatus | None = None
    role: UserRole | None = None
    current_password: str | None = None


class AdminResetPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)
    # step-up 窗口内可省略：30 分钟内已复核过管理员密码。
    current_password: str | None = Field(default=None, min_length=1, max_length=128)


class AdminDeleteUser(BaseModel):
    # 删除账号属于不可逆操作：要求管理员本人当前密码复核，
    # 防止会话被临时窃取后静默删除用户；step-up 窗口内可省略。
    current_password: str | None = Field(default=None, min_length=1, max_length=128)


class AdminCreateUser(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole | None = None
    status: UserStatus | None = None


class AdminInviteUser(BaseModel):
    email: EmailStr
    nickname: str | None = Field(default=None, min_length=1, max_length=80)


class AdminBatchUserUpdate(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    status: UserStatus | None = None
    role: UserRole | None = None
    current_password: str | None = None


class AdminBatchDeleteUser(BaseModel):
    user_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)
    current_password: str | None = Field(default=None, min_length=1, max_length=128)


class AdminBatchInviteUser(BaseModel):
    emails: list[EmailStr] = Field(min_length=1, max_length=100)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "kind": "user",
        "email": user.email,
        "nickname": user.nickname,
        "phone": user.phone,
        "email_verified": user.email_verified_at is not None,
        "role": user.role.value,
        "status": user.status.value,
        "created_at": user.created_at,
        "expires_at": None,
    }


def _serialize_invite(invite: AccountInvite, now: datetime) -> dict:
    if invite.cancelled_at is not None:
        status = "cancelled"
    elif invite.used_at is not None:
        status = "used"
    elif _as_utc(invite.expires_at) <= now:
        status = "expired"
    else:
        status = "invited"
    return {
        "id": str(invite.id),
        "kind": "invite",
        "email": invite.email,
        "nickname": invite.nickname,
        "phone": None,
        "email_verified": False,
        "role": None,
        "status": status,
        "created_at": invite.created_at,
        "expires_at": invite.expires_at,
        "used_at": invite.used_at,
        "cancelled_at": invite.cancelled_at,
    }


@router.get("/users", response_model=list[dict])
def list_users(
    q: str | None = Query(None, max_length=100),
    status: str | None = Query(
        None, pattern="^(active|disabled|invited|expired|cancelled|used)$"
    ),
    role: str | None = Query(None, pattern="^(user|admin)$"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    user_stmt = select(User)
    invite_stmt = select(AccountInvite)
    if q:
        pattern = f"%{q}%"
        user_stmt = user_stmt.where(
            or_(User.email.ilike(pattern), User.nickname.ilike(pattern))
        )
        invite_stmt = invite_stmt.where(
            or_(
                AccountInvite.email.ilike(pattern),
                AccountInvite.nickname.ilike(pattern),
            )
        )

    now = datetime.now(timezone.utc)
    registered_emails = set(db.scalars(select(User.email)).all())
    rows = [
        {"created_at": user.created_at, "item": _serialize_user(user)}
        for user in db.scalars(user_stmt).all()
    ]
    rows.extend(
        {
            "created_at": invite.created_at,
            "item": _serialize_invite(invite, now),
        }
        for invite in db.scalars(invite_stmt).all()
        # 已使用且邮箱仍注册的邀请由用户行展示，避免重复；
        # 账号被删除的邀请在删除时已还原为“待注册”。
        if invite.used_at is None or invite.email not in registered_emails
    )
    if status:
        rows = [row for row in rows if row["item"]["status"] == status]
    if role:
        rows = [row for row in rows if row["item"]["role"] == role]
    # 已注册用户与待注册邀请按创建时间倒序合并展示，
    # 方便管理员在用户栏直接看到每封邀请所处的状态。
    rows.sort(key=lambda row: _as_utc(row["created_at"]), reverse=True)
    return [row["item"] for row in rows[:limit]]


@router.post("/users", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminCreateUser,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    user = User(
        email=email,
        nickname=payload.nickname,
        password_hash=hash_password(payload.password),
        role=payload.role or UserRole.user,
        status=payload.status or UserStatus.active,
        # 管理员代建账号视为已完成邮箱验证；邀请注册则必须由受邀者激活。
        email_verified_at=datetime.now(timezone.utc),
        # 强制 2FA：代建账号直接启用邮箱验证码作为默认第二方案。
        email_otp_enabled=True,
    )
    db.add(user)
    db.commit()
    invalidate_admin_stats_cache()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_create_user",
        category="admin_user",
        target_type="user",
        target_id=str(user.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"email": email, "role": user.role.value},
    )
    return _serialize_user(user)


@router.post("/users/invite")
def invite_user(
    payload: AdminInviteUser,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    settings = get_settings()
    invite_count = get_rate_limiter().hit(
        "admin_invite", ip, settings.admin_invite_rate_window_seconds
    )
    if invite_count > settings.admin_invite_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_invite",
            invite_count,
            settings.admin_invite_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            ip=ip,
            detail={"action": "admin_invite", "reason": "rate_limit"},
        )
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送邀请过于频繁，请稍后再试")
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")
    now = datetime.now(timezone.utc)
    pending = db.scalar(
        select(AccountInvite).where(
            AccountInvite.email == email,
            AccountInvite.used_at.is_(None),
            AccountInvite.cancelled_at.is_(None),
        )
    )
    if pending is not None and _as_utc(pending.expires_at) > now:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已收到邀请，请勿重复发送")

    token = generate_token()
    invite = AccountInvite(
        email=email,
        nickname=payload.nickname,
        token_hash=hash_token(token),
        created_by=actor.id,
        expires_at=now + timedelta(days=settings.invite_ttl_days),
    )
    db.add(invite)
    db.commit()
    link = f"{settings.frontend_base_url.rstrip('/')}/invite?token={token}"
    try:
        get_email_service().send_invite(email, link)
    except Exception:
        # 邮件发送失败时不留下“幽灵邀请”：删除邀请行并返回明确错误，
        # 避免管理员以为已发送、受邀者却收不到邮件。
        logger.exception("邀请邮件发送失败：%s", email)
        db.delete(invite)
        db.commit()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "邮件发送失败，请检查邮件服务配置"
        )
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_invite_user",
        category="admin_user",
        target_type="user",
        target_id=email,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={"email": email},
    )
    return {"message": "邀请邮件已发送"}


@router.post("/users/invites/{invite_id:uuid}/cancel")
def cancel_invite(
    invite_id: uuid.UUID,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    invite = db.get(AccountInvite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请不存在")
    if invite.used_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该邀请已被使用，无法取消")
    if invite.cancelled_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "该邀请已取消")

    invite.cancelled_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_cancel_invite",
        category="admin_user",
        target_type="invite",
        target_id=str(invite.id),
        detail={"email": invite.email},
    )
    return {"message": "邀请已取消，原链接立即失效"}


@router.post("/users/invites/{invite_id:uuid}/resend")
def resend_invite(
    invite_id: uuid.UUID,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    settings = get_settings()
    resend_count = get_rate_limiter().hit(
        "admin_invite", ip, settings.admin_invite_rate_window_seconds
    )
    if resend_count > settings.admin_invite_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_resend_invite",
            resend_count,
            settings.admin_invite_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            ip=ip,
            detail={"action": "admin_resend_invite", "reason": "rate_limit"},
        )
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送邀请过于频繁，请稍后再试")

    invite = db.get(AccountInvite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请不存在")
    if db.scalar(select(User).where(User.email == invite.email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册，无需重发邀请")

    now = datetime.now(timezone.utc)
    token = generate_token()
    token_hash = hash_token(token)
    if invite.used_at is None:
        # 待注册/已过期/已取消：复用原记录，轮换令牌并顺延有效期，旧链接立即失效。
        invite.token_hash = token_hash
        invite.expires_at = now + timedelta(days=settings.invite_ttl_days)
        invite.cancelled_at = None
        target = invite
    else:
        # 已使用（注册后账号被删除）：为同一邮箱创建全新邀请，
        # 原邀请保留为历史记录；若已存在有效邀请则直接复用，避免同一邮箱出现多个有效链接。
        existing_pending = db.scalar(
            select(AccountInvite).where(
                AccountInvite.email == invite.email,
                AccountInvite.id != invite.id,
                AccountInvite.used_at.is_(None),
                AccountInvite.cancelled_at.is_(None),
            )
        )
        if existing_pending is not None:
            existing_pending.token_hash = token_hash
            existing_pending.expires_at = now + timedelta(
                days=settings.invite_ttl_days
            )
            target = existing_pending
        else:
            target = AccountInvite(
                email=invite.email,
                nickname=invite.nickname,
                token_hash=token_hash,
                created_by=actor.id,
                expires_at=now + timedelta(days=settings.invite_ttl_days),
            )
            db.add(target)

    link = f"{settings.frontend_base_url.rstrip('/')}/invite?token={token}"
    try:
        get_email_service().send_invite(invite.email, link)
    except Exception:
        # 邮件发送失败时回滚令牌轮换/新邀请，避免留下无法收到邮件的“幽灵邀请”。
        db.rollback()
        logger.exception("重发邀请邮件失败：%s", invite.email)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "邮件发送失败，请检查邮件服务配置"
        )
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_resend_invite",
        category="admin_user",
        target_type="invite",
        target_id=str(invite.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={"email": invite.email},
    )
    return {"message": "邀请已重新发送"}


@router.post("/users/invites/{invite_id:uuid}/delete")
def delete_invite(
    invite_id: uuid.UUID,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    invite = db.get(AccountInvite, invite_id)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "邀请不存在")
    email = invite.email
    db.delete(invite)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_delete_invite",
        category="admin_user",
        target_type="invite",
        target_id=str(invite_id),
        detail={"email": email},
    )
    return {"message": "邀请记录已删除"}


@router.post("/users/batch/invite")
def batch_invite_users(
    payload: AdminBatchInviteUser,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    ip = request.client.host if request.client else ""
    settings = get_settings()
    emails = list(dict.fromkeys(email.lower() for email in payload.emails))
    batch_count = get_rate_limiter().hit(
        "admin_invite",
        ip,
        settings.admin_invite_rate_window_seconds,
        len(emails),
    )
    if batch_count > settings.admin_invite_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_batch_invite",
            batch_count,
            settings.admin_invite_rate_limit,
            increment=len(emails),
            actor_type="admin",
            actor_id=str(actor.id),
            ip=ip,
            detail={"action": "admin_batch_invite", "reason": "rate_limit"},
        )
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送邀请过于频繁，请稍后再试")

    now = datetime.now(timezone.utc)
    existing = set(
        db.scalars(select(User.email).where(User.email.in_(emails)))
    )
    pending_rows = db.scalars(
        select(AccountInvite).where(
            AccountInvite.email.in_(emails),
            AccountInvite.used_at.is_(None),
            AccountInvite.cancelled_at.is_(None),
        )
    ).all()
    pending_emails = {
        row.email for row in pending_rows if _as_utc(row.expires_at) > now
    }

    invited: list[str] = []
    skipped: list[dict] = []
    failed: list[dict] = []
    pending_invites: list[tuple[AccountInvite, str]] = []
    for email in emails:
        if email in existing:
            skipped.append({"email": email, "reason": "already_registered"})
            continue
        if email in pending_emails:
            skipped.append({"email": email, "reason": "already_invited"})
            continue

        token = generate_token()
        invite = AccountInvite(
            email=email,
            nickname=None,
            token_hash=hash_token(token),
            created_by=actor.id,
            expires_at=now + timedelta(days=settings.invite_ttl_days),
        )
        db.add(invite)
        db.commit()
        link = f"{settings.frontend_base_url.rstrip('/')}/invite?token={token}"
        pending_invites.append((invite, link))

    if pending_invites:
        results = get_email_service().send_invite_batch(
            [(invite.email, link) for invite, link in pending_invites]
        )
        for (invite, _link), result in zip(pending_invites, results):
            if result is None:
                invited.append(invite.email)
                continue
            logger.error(
                "邀请邮件发送失败：%s error=%s", invite.email, result
            )
            db.delete(invite)
            db.commit()
            failed.append({"email": invite.email, "reason": "邮件发送失败"})

    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_batch_invite_user",
        category="admin_user",
        target_type="user",
        target_id=None,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={
            "invited": invited,
            "skipped": skipped,
            "failed": failed,
        },
    )
    return {"invited": invited, "skipped": skipped, "failed": failed}


@router.patch("/users/batch", response_model=dict)
def batch_update_users(
    payload: AdminBatchUserUpdate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    if payload.status is None and payload.role is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "至少指定一项要修改的状态或角色"
        )
    user_ids = list(dict.fromkeys(payload.user_ids))
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    by_id = {user.id: user for user in users}
    missing = [str(uid) for uid in user_ids if uid not in by_id]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"部分用户不存在：{','.join(missing[:5])}",
        )
    if actor.id in by_id:
        if payload.status == UserStatus.disabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能批量禁用自己")
        if payload.role is not None and payload.role != UserRole.admin:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "不能批量取消自己的管理员角色"
            )
    if payload.role is not None:
        session = get_current_session(request, db)
        authorize_stepup(request, db, actor, session, payload.current_password)

    for user in users:
        if payload.status is not None:
            user.status = payload.status
        if payload.role is not None:
            user.role = payload.role
    db.commit()
    invalidate_admin_stats_cache()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_batch_update_user",
        category="admin_user",
        target_type="user",
        target_id=None,
        detail={
            "emails": [user.email for user in users],
            "status": payload.status.value if payload.status else None,
            "role": payload.role.value if payload.role else None,
        },
    )
    return {"updated": [_serialize_user(user) for user in users]}


@router.patch("/users/{user_id:uuid}", response_model=dict)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.id == actor.id:
        if payload.status == UserStatus.disabled:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能禁用自己")
        if payload.role is not None and payload.role != UserRole.admin:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能取消自己的管理员角色")
    if payload.role is not None:
        session = get_current_session(request, db)
        authorize_stepup(request, db, actor, session, payload.current_password)
    if payload.status is not None:
        user.status = payload.status
    if payload.role is not None:
        user.role = payload.role
    db.commit()
    invalidate_admin_stats_cache()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_update_user",
        category="admin_user",
        target_type="user",
        target_id=str(user.id),
        detail={
            "status": user.status.value,
            "role": user.role.value,
        },
    )
    return _serialize_user(user)


@router.post("/users/{user_id:uuid}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    payload: AdminResetPassword,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    session = get_current_session(request, db)
    authorize_stepup(request, db, actor, session, payload.current_password)
    user.password_hash = hash_password(payload.new_password)
    sessions = db.scalars(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.revoked_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for session in sessions:
        session.revoked_at = now
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_reset_password",
        category="admin_user",
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "密码已重置，该用户所有会话已退出"}


@router.post("/users/{user_id}/reset-2fa")
def reset_twofa(
    user_id: uuid.UUID,
    payload: PasswordConfirm,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    session = get_current_session(request, db)
    authorize_stepup(request, db, actor, session, payload.current_password)
    # 2FA 被重置后，旧会话（可能基于 2FA 建立）一并失效。
    sessions = db.scalars(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.revoked_at.is_(None),
        )
    ).all()
    now = datetime.now(timezone.utc)
    for session in sessions:
        session.revoked_at = now
    user.totp_secret_encrypted = None
    user.totp_enabled_at = None
    # 强制 2FA：管理端重置不把账号清成 1FA，
    # 而是恢复默认邮箱验证码方案（TOTP 与恢复码全部清空）。
    user.email_otp_enabled = True
    codes = db.scalars(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ).all()
    for code in codes:
        db.delete(code)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_reset_2fa",
        category="admin_user",
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "已重置该用户的二次验证"}


@router.post("/users/batch/delete")
def batch_delete_users(
    payload: AdminBatchDeleteUser,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    session = get_current_session(request, db)
    authorize_stepup(request, db, actor, session, payload.current_password)
    user_ids = list(dict.fromkeys(payload.user_ids))
    users = db.scalars(select(User).where(User.id.in_(user_ids))).all()
    by_id = {user.id: user for user in users}
    missing = [str(uid) for uid in user_ids if uid not in by_id]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"部分用户不存在：{','.join(missing[:5])}",
        )
    if actor.id in by_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "不能批量删除自己的账号，请使用账号注销功能"
        )
    admins = [user for user in users if user.role == UserRole.admin]
    if admins:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "不能直接删除管理员账号，请先将其降级为普通用户",
        )

    deleted = [{"id": str(user.id), "email": user.email} for user in users]
    notification_targets = [
        {"email": user.email, "nickname": user.nickname} for user in users
    ]
    for user in users:
        delete_user_account(db, user, commit=False)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_batch_delete_user",
        category="admin_user",
        target_type="user",
        target_id=None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={
            "ids": [item["id"] for item in deleted],
            "emails": [item["email"] for item in deleted],
        },
    )
    for target in notification_targets:
        try:
            get_email_service().send_account_deleted(
                target["email"], target["nickname"]
            )
        except Exception:
            logger.exception(
                "账号删除通知邮件发送失败：%s", target["email"]
            )
    return {"message": f"已删除 {len(deleted)} 个账号", "deleted": deleted}


@router.post("/users/{user_id:uuid}/delete")
def delete_user(
    user_id: uuid.UUID,
    payload: AdminDeleteUser,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.id == actor.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "不能删除自己的账号，请使用账号注销功能"
        )
    if user.role == UserRole.admin:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "不能直接删除管理员账号，请先将其降级为普通用户",
        )
    session = get_current_session(request, db)
    authorize_stepup(request, db, actor, session, payload.current_password)

    user_email = user.email
    user_nickname = user.nickname
    delete_user_account(db, user)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_delete_user",
        category="admin_user",
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"email": user.email},
    )
    try:
        get_email_service().send_account_deleted(user_email, user_nickname)
    except Exception:
        logger.exception("账号删除通知邮件发送失败：%s", user_email)
    return {"message": "账号已删除"}


@router.get("/audit-logs", response_model=list[dict])
def list_audit_logs(
    category: str | None = Query(None),
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(AuditLog)
    if category:
        stmt = stmt.where(AuditLog.category == category)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor_id:
        stmt = stmt.where(AuditLog.actor_id == actor_id)
    if start:
        stmt = stmt.where(AuditLog.created_at >= start)
    if end:
        stmt = stmt.where(AuditLog.created_at <= end)
    logs = db.scalars(
        stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [
        {
            "id": str(log.id),
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "action": log.action,
            "category": log.category,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "ip": log.ip,
            "ip_location": describe_ip(log.ip),
            "detail": log.detail,
            "created_at": log.created_at,
        }
        for log in logs
    ]
