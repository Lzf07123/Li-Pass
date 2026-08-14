from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.core.redis import get_redis_client
from app.models.user import User
from app.services.audit import log_audit
from app.services.system_info import collect_system_info

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-system"],
    dependencies=[Depends(get_current_admin)],
)


def _database_status(db: Session) -> str:
    try:
        db.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


def _redis_status() -> str:
    settings = get_settings()
    uses_redis = (
        settings.pending_request_store == "redis"
        or settings.twofa_store == "redis"
        or settings.rate_limiter == "redis"
    )
    if not uses_redis:
        return "unused"
    try:
        get_redis_client().ping()
        return "ok"
    except Exception:
        return "error"


@router.get("/system")
def get_system_info(
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """返回宿主机与进程的运行信息快照，仅管理员可访问。"""
    info = collect_system_info()
    info["services"] = {
        "database": _database_status(db),
        "redis": _redis_status(),
    }
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_view_system",
        category="admin_settings",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return info
