from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.user import User
from app.services.audit import log_audit
from app.services.admin_stats import collect_admin_stats

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-stats"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("/stats")
def get_admin_stats(
    request: Request,
    days: int = Query(30, ge=7, le=90),
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """返回账号、登录趋势与认证方式分布的统计快照，仅管理员可访问。"""
    result = collect_admin_stats(db, days)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_view_stats",
        category="admin_settings",
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"days": days},
    )
    return result
