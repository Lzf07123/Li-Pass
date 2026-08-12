import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_token, hash_token
from app.services.account_deletion import delete_user_account
from app.services.audit import log_audit
from app.services.email import get_email_service
from app.services.rate_limit import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin)],
)


class AdminUserUpdate(BaseModel):
    status: UserStatus | None = None
    role: UserRole | None = None


class AdminResetPassword(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class AdminDeleteUser(BaseModel):
    # 删除账号属于不可逆操作：要求管理员本人当前密码复核，
    # 防止会话被临时窃取后静默删除用户。
    current_password: str = Field(min_length=1, max_length=128)


class AdminCreateUser(BaseModel):
    email: EmailStr
    nickname: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole | None = None
    status: UserStatus | None = None


class AdminInviteUser(BaseModel):
    email: EmailStr
    nickname: str | None = Field(default=None, min_length=1, max_length=80)


def _serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "nickname": user.nickname,
        "phone": user.phone,
        "email_verified": user.email_verified_at is not None,
        "role": user.role.value,
        "status": user.status.value,
        "created_at": user.created_at,
    }


@router.get("/users", response_model=list[dict])
def list_users(
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if q:
        stmt = stmt.where(
            or_(User.email.ilike(f"%{q}%"), User.nickname.ilike(f"%{q}%"))
        )
    return [_serialize_user(user) for user in db.scalars(stmt).all()]


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
    )
    db.add(user)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_create_user",
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
    if (
        get_rate_limiter().hit(
            "admin_invite", ip, settings.register_rate_window_seconds
        )
        > settings.register_rate_limit
    ):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "发送邀请过于频繁，请稍后再试")
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "该邮箱已注册")

    token = generate_token()
    invite = AccountInvite(
        email=email,
        nickname=payload.nickname,
        token_hash=hash_token(token),
        created_by=actor.id,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.invite_ttl_days),
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
        target_type="user",
        target_id=email,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={"email": email},
    )
    return {"message": "邀请邮件已发送"}


@router.patch("/users/{user_id:uuid}", response_model=dict)
def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
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
    if payload.status is not None:
        user.status = payload.status
    if payload.role is not None:
        user.role = payload.role
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_update_user",
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
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
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
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "密码已重置，该用户所有会话已退出"}


@router.post("/users/{user_id}/reset-2fa")
def reset_twofa(
    user_id: uuid.UUID,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
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
    user.email_otp_enabled = False
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
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "已重置该用户的二次验证"}


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
    if not verify_password(payload.current_password, actor.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")

    delete_user_account(db, user)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_delete_user",
        target_type="user",
        target_id=str(user_id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"email": user.email},
    )
    return {"message": "账号已删除"}


@router.get("/audit-logs", response_model=list[dict])
def list_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    logs = db.scalars(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": str(log.id),
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "ip": log.ip,
            "detail": log.detail,
            "created_at": log.created_at,
        }
        for log in logs
    ]
