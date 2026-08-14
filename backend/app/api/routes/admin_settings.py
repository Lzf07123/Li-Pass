import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.ip2region_progress import (
    UpdateProgress,
    get_progress_store,
)
from app.services.ip2region_update import ip2region_status, run_update_task
from app.services.rate_limit import get_rate_limiter
from app.services.site_settings import (
    PUBLIC_REGISTRATION_ENABLED_KEY,
    get_site_setting_bool,
    set_site_setting_bool,
    set_site_setting_int,
)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_admin)],
)


class SiteSettingsUpdate(BaseModel):
    public_registration_enabled: bool | None = None
    ip2region_auto_update_enabled: bool | None = None
    ip2region_update_interval_hours: int | None = Field(None, ge=1, le=8760)


@router.get("/settings", response_model=dict)
def get_site_settings(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return {
        "public_registration_enabled": get_site_setting_bool(
            db,
            PUBLIC_REGISTRATION_ENABLED_KEY,
            settings.public_registration_enabled,
        ),
        "ip2region": ip2region_status(db),
    }


@router.put("/settings", response_model=dict)
def update_site_settings(
    payload: SiteSettingsUpdate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    # 字段可选（PATCH 语义）：只更新显式传入的项，避免两个管理员并发
    # 保存时用旧快照覆盖对方刚改过的公开注册开关。
    detail: dict = {}
    if payload.public_registration_enabled is not None:
        set_site_setting_bool(
            db,
            PUBLIC_REGISTRATION_ENABLED_KEY,
            payload.public_registration_enabled,
        )
        detail.update(
            {
                "key": PUBLIC_REGISTRATION_ENABLED_KEY,
                "value": payload.public_registration_enabled,
            }
        )
    if payload.ip2region_auto_update_enabled is not None:
        set_site_setting_bool(
            db,
            "ip2region_auto_update_enabled",
            payload.ip2region_auto_update_enabled,
        )
        detail["ip2region_auto_update_enabled"] = (
            payload.ip2region_auto_update_enabled
        )
    if payload.ip2region_update_interval_hours is not None:
        set_site_setting_int(
            db,
            "ip2region_update_interval_hours",
            payload.ip2region_update_interval_hours,
        )
        detail["ip2region_update_interval_hours"] = (
            payload.ip2region_update_interval_hours
        )
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_update_site_setting",
        category="admin_settings",
        target_type="setting",
        target_id=PUBLIC_REGISTRATION_ENABLED_KEY,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail=detail,
    )
    return {
        "public_registration_enabled": get_site_setting_bool(
            db,
            PUBLIC_REGISTRATION_ENABLED_KEY,
            get_settings().public_registration_enabled,
        ),
        "ip2region": ip2region_status(db),
    }


@router.post(
    "/settings/ip2region/update",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
)
async def update_ip2region_db(
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """后台检查并更新 ip2region 离线库，立即返回；进度经 status 接口轮询。"""
    settings = get_settings()
    count = get_rate_limiter().hit(
        "admin_ip2region_update",
        str(actor.id),
        settings.ip2region_update_rate_window_seconds,
    )
    if count > settings.ip2region_update_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_ip2region_update",
            count,
            settings.ip2region_update_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            detail={"action": "admin_ip2region_update", "reason": "rate_limit"},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "操作过于频繁，请稍后再试"
        )
    store = get_progress_store()
    if store.get()["state"] == "running":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "已有更新任务进行中，请稍后再试（可在状态接口查看进度）",
        )
    started_at = datetime.now(timezone.utc).isoformat()
    store.set(
        UpdateProgress(state="running", stage="checking", started_at=started_at)
    )
    # 后台任务使用独立 DB 会话：请求结束（会话关闭）后下载仍继续。
    # dependency_overrides 让测试环境注入内存 SQLite 会话工厂。
    db_factory = request.app.dependency_overrides.get(get_db, get_db)
    asyncio.create_task(
        asyncio.to_thread(
            run_update_task,
            db_factory,
            str(actor.id),
            request.client.host if request.client else None,
            request.headers.get("user-agent"),
            started_at,
        )
    )
    return {"started": True, "status": store.get()}


@router.get("/settings/ip2region/update/status", response_model=dict)
def get_ip2region_update_status() -> dict:
    """返回后台更新任务的进度快照；从未启动时为 idle。"""
    return get_progress_store().get()
