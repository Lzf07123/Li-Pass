import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.security.passwords import hash_password
from app.services.audit import log_audit

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
        str(user.id),
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
        str(user.id),
        "admin_reset_password",
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "密码已重置，该用户所有会话已退出"}


@router.post("/users/{user_id}/reset-2fa")
def reset_twofa(user_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
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
        str(user.id),
        "admin_reset_2fa",
        target_type="user",
        target_id=str(user.id),
    )
    return {"message": "已重置该用户的二次验证"}


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
