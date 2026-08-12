from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models.user import User
from app.services.audit import log_audit
from app.services.site_settings import (
    PUBLIC_REGISTRATION_ENABLED_KEY,
    get_site_setting_bool,
    set_site_setting_bool,
)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-settings"],
    dependencies=[Depends(get_current_admin)],
)


class SiteSettingsUpdate(BaseModel):
    public_registration_enabled: bool


@router.get("/settings", response_model=dict)
def get_site_settings(db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    return {
        "public_registration_enabled": get_site_setting_bool(
            db,
            PUBLIC_REGISTRATION_ENABLED_KEY,
            settings.public_registration_enabled,
        )
    }


@router.put("/settings", response_model=dict)
def update_site_settings(
    payload: SiteSettingsUpdate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    set_site_setting_bool(
        db,
        PUBLIC_REGISTRATION_ENABLED_KEY,
        payload.public_registration_enabled,
    )
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_update_site_setting",
        target_type="setting",
        target_id=PUBLIC_REGISTRATION_ENABLED_KEY,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={
            "key": PUBLIC_REGISTRATION_ENABLED_KEY,
            "value": payload.public_registration_enabled,
        },
    )
    return {"public_registration_enabled": payload.public_registration_enabled}
