import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_session
from app.core.config import get_settings
from app.core.db import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.auth import AdminSessionListOut
from app.services.audit import log_audit

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-sessions"],
    dependencies=[Depends(get_current_admin)],
)


def _serialize_session(session: SessionModel, user: User, current: bool) -> dict:
    return {
        "id": str(session.id),
        "user": {
            "id": str(user.id),
            "email": user.email,
            "nickname": user.nickname,
            "role": user.role.value,
            "status": user.status.value,
        },
        "auth_method": session.auth_method,
        "device_name": session.device_name,
        "ip": session.ip,
        "user_agent": session.user_agent,
        "created_at": session.created_at,
        "last_used_at": session.last_used_at,
        "expires_at": session.expires_at,
        "current": current,
    }


@router.get("/sessions", response_model=AdminSessionListOut)
def list_sessions(
    request: Request,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    """列出全站仍在线的门户会话，供管理员监控并手动强制下线。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    idle_cutoff = now - timedelta(days=settings.session_idle_days)

    # 已过期或空闲超时的会话视为已下线，先批量吊销，避免“僵尸”记录；
    # 用 SQL UPDATE 一次处理，而不是全量加载后在 Python 里逐条判断。
    db.execute(
        update(SessionModel)
        .where(
            SessionModel.revoked_at.is_(None),
            or_(
                SessionModel.expires_at < now,
                SessionModel.last_used_at < idle_cutoff,
            ),
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    db.commit()

    stmt = (
        select(SessionModel, User)
        .join(User, SessionModel.user_id == User.id)
        .where(SessionModel.revoked_at.is_(None))
        .order_by(SessionModel.last_used_at.desc())
    )
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                User.email.ilike(pattern),
                User.nickname.ilike(pattern),
                SessionModel.ip.ilike(pattern),
                SessionModel.device_name.ilike(pattern),
            )
        )

    total = (
        db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    )
    current = get_current_session(request, db)
    rows = db.execute(stmt.offset(offset).limit(limit)).all()
    return {
        "items": [
            _serialize_session(session, user, session.id == current.id)
            for session, user in rows
        ],
        "total": total,
    }


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    """管理员强制下线指定会话；被踢出的用户需重新登录。"""
    session = db.get(SessionModel, session_id)
    if session is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    current = get_current_session(request, db)
    if session.id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能下线当前会话")
    if session.revoked_at is not None:
        # 并发重复操作：会话已下线，幂等返回成功。
        return

    user = db.get(User, session.user_id)
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_revoke_session",
        target_type="session",
        target_id=str(session.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={
            "email": user.email if user else None,
            "user_id": str(session.user_id),
            "device_name": session.device_name,
            "ip": session.ip,
        },
    )
