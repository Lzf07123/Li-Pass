import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, get_current_session
from app.core.config import get_settings
from app.core.db import get_db
from app.models.session import Session as SessionModel
from app.models.user import User
from app.schemas.auth import AdminSessionListOut
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.device_info import describe_session_device
from app.services.federated_logout import (
    collect_logout_targets,
    dispatch_backchannel_logout,
    revoke_session_links,
)
from app.services.geoip import describe_ip
from app.services.rate_limit import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-sessions"],
    dependencies=[Depends(get_current_admin)],
)


class AdminBatchRevokeSessions(BaseModel):
    session_ids: list[uuid.UUID] = Field(min_length=1, max_length=200)


def _enforce_revoke_rate_limit(actor: User, db: Session) -> None:
    """批量/全部下线属于高影响管理操作，按管理员维度限流兜底。"""
    settings = get_settings()
    count = get_rate_limiter().hit(
        "admin_session_revoke",
        str(actor.id),
        settings.admin_session_revoke_rate_window_seconds,
    )
    if count > settings.admin_session_revoke_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_session_revoke",
            count,
            settings.admin_session_revoke_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            detail={"action": "admin_session_revoke", "reason": "rate_limit"},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "操作过于频繁，请稍后再试"
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
        "device_name": describe_session_device(
            session.device_name, session.user_agent
        ),
        "ip": session.ip,
        "ip_location": describe_ip(session.ip),
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
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)

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


@router.post("/sessions/batch-revoke", response_model=dict)
def batch_revoke_sessions(
    payload: AdminBatchRevokeSessions,
    request: Request,
    background_tasks: BackgroundTasks,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """批量强制下线指定会话。

    当前会话、已下线或不存在的会话自动跳过（幂等），不视为错误；
    响应返回实际下线的数量与被跳过的数量。
    """
    _enforce_revoke_rate_limit(actor, db)
    current = get_current_session(request, db)
    ids = list(dict.fromkeys(payload.session_ids))
    rows = db.execute(
        select(SessionModel, User)
        .join(User, SessionModel.user_id == User.id)
        .where(
            SessionModel.id.in_(ids),
            SessionModel.revoked_at.is_(None),
            SessionModel.id != current.id,
        )
    ).all()
    revoked = []
    for session, user in rows:
        session.revoked_at = datetime.now(timezone.utc)
        revoked.append((session, user))
    db.commit()
    targets = collect_logout_targets(
        db, [session.id for session, _ in revoked]
    )
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    revoke_session_links(db, [session.id for session, _ in revoked])
    skipped = len(ids) - len(revoked)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_batch_revoke_session",
        target_type="session",
        target_id=None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={
            "count": len(revoked),
            "skipped": skipped,
            "emails": [user.email for _, user in revoked],
            "user_ids": [str(session.user_id) for session, _ in revoked],
        },
    )
    return {"revoked": len(revoked), "skipped": skipped}


@router.post("/sessions/revoke-all", response_model=dict)
def revoke_all_sessions(
    request: Request,
    background_tasks: BackgroundTasks,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """下线除当前会话外的全部在线会话；当前会话不受影响。"""
    _enforce_revoke_rate_limit(actor, db)
    settings = get_settings()
    now = datetime.now(timezone.utc)
    idle_cutoff = now - timedelta(minutes=settings.session_idle_minutes)
    # 先清理过期/空闲超时的“僵尸”会话，与列表接口口径一致，
    # 避免把它们也算进“在线”数量。
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
    current = get_current_session(request, db)
    target_ids = db.scalars(
        select(SessionModel.id).where(
            SessionModel.revoked_at.is_(None),
            SessionModel.id != current.id,
        )
    ).all()
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.revoked_at.is_(None),
            SessionModel.id != current.id,
        )
        .values(revoked_at=now)
        .execution_options(synchronize_session=False)
    )
    count = result.rowcount or 0
    db.commit()
    targets = collect_logout_targets(db, list(target_ids))
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    revoke_session_links(db, list(target_ids))
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_revoke_all_sessions",
        target_type="session",
        target_id=None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"count": count},
    )
    return {"revoked": count}


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    background_tasks: BackgroundTasks,
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
    targets = collect_logout_targets(db, [session.id])
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    revoke_session_links(db, [session.id])
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
