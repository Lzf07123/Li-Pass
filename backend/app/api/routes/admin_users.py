import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.audit_log import AuditLog
from app.models.recovery_code import RecoveryCode
from app.models.user import User
from app.services.audit import log_audit

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-users"],
    dependencies=[Depends(get_current_admin)],
)


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
