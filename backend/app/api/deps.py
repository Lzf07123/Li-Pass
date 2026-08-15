from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import LEGACY_SESSION_COOKIE_NAME, get_settings
from app.core.db import get_db
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.security.tokens import hash_token

# 会话最近活动时间只需低频刷新：写操作（UPDATE + COMMIT）比读查询贵得多，
# 高频接口（/me、/oauth2/authorize 等）不应为每个请求都触发一次数据库写入。
_LAST_USED_REFRESH_INTERVAL = timedelta(minutes=5)


def _as_utc(dt: datetime) -> datetime:
    """Normalize a possibly naive datetime to UTC for comparison."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _load_identity(request: Request, db: Session) -> tuple[SessionModel, User]:
    """单请求内缓存鉴权结果，避免会话/用户被重复查询。

    一个请求里常同时依赖 session 与 user（例如授权确认、会话列表），
    此前每次依赖解析都会分别查一次 sessions 和 users 表；
    现在同一请求只查一次，后续依赖直接复用 request.state。
    """
    cached = getattr(request.state, "auth_identity", None)
    if cached is not None:
        return cached

    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name) or request.cookies.get(
        LEGACY_SESSION_COOKIE_NAME
    )
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    session = db.scalar(
        select(SessionModel).where(SessionModel.token_hash == hash_token(token))
    )
    now = datetime.now(timezone.utc)
    idle_cutoff = now - timedelta(days=settings.session_idle_days)
    if (
        session is None
        or session.revoked_at is not None
        or _as_utc(session.expires_at) < now
        or _as_utc(session.last_used_at) < idle_cutoff
    ):
        if session is not None and session.revoked_at is None:
            # 超时会话直接吊销，避免留下永不活跃的“僵尸”会话记录。
            session.revoked_at = now
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

    user = db.get(User, session.user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User unavailable")

    # 低频刷新最近活动时间：超过 5 分钟才写一次；刚写过的不再产生写事务。
    if now - _as_utc(session.last_used_at) >= _LAST_USED_REFRESH_INTERVAL:
        db.execute(
            update(SessionModel)
            .where(SessionModel.id == session.id)
            .values(last_used_at=now)
        )
        db.commit()

    request.state.auth_identity = (session, user)
    return session, user


def get_current_session(request: Request, db: Session = Depends(get_db)) -> SessionModel:
    session, _ = _load_identity(request, db)
    return session


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    _, user = _load_identity(request, db)
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


def get_optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    try:
        return get_current_user(request, db)
    except HTTPException:
        return None


def get_optional_session(
    request: Request, db: Session = Depends(get_db)
) -> SessionModel | None:
    """OIDC end-session 等端点需要区分“无会话”与“会话失效”之外的场景。"""
    try:
        return get_current_session(request, db)
    except HTTPException:
        return None


def clear_session_cookie(response) -> None:
    """删除门户会话 Cookie；属性必须与设置时一致（Secure/SameSite/HttpOnly），
   否则 HTTPS 生产环境浏览器可能不认可删除指令。"""
    settings = get_settings()
    for name in (settings.session_cookie_name, LEGACY_SESSION_COOKIE_NAME):
        response.delete_cookie(
            name,
            secure=settings.session_cookie_secure,
            httponly=True,
            samesite=settings.session_cookie_samesite,
        )
