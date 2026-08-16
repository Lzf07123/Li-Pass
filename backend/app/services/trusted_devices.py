"""登录可信设备：授予、校验与撤销。"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.trusted_device import TrustedDevice
from app.security.tokens import generate_token, hash_token
from app.services.device_info import (
    build_device_label,
    parse_ch_headers,
    parse_user_agent,
)

TRUSTED_DEVICE_COOKIE = "lipass_trusted_device"


def _as_utc(dt: datetime) -> datetime:
    """SQLite 读取时区列会得到 naive datetime，统一归一化到 UTC 再比较。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _device_label(request: Request) -> str:
    headers = request.headers
    fingerprint = (
        parse_ch_headers(headers)
        if headers.get("sec-ch-ua-model") or headers.get("sec-ch-ua-platform")
        else parse_user_agent(headers.get("user-agent", ""))
    )
    return build_device_label(fingerprint)[:120]


def set_trusted_device_cookie(response: Response, token: str, ttl: timedelta) -> None:
    settings = get_settings()
    response.set_cookie(
        TRUSTED_DEVICE_COOKIE,
        token,
        max_age=int(ttl.total_seconds()),
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def clear_trusted_device_cookie(response: Response) -> None:
    """删除可信设备 Cookie；属性与设置时一致，确保生产 HTTPS 下可被清除。"""
    settings = get_settings()
    response.delete_cookie(
        TRUSTED_DEVICE_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite=settings.session_cookie_samesite,
    )


def grant(db: Session, user_id: uuid.UUID, request: Request, response: Response) -> TrustedDevice:
    """为当前用户授予一台可信设备，并写入浏览器 Cookie。"""
    now = datetime.now(timezone.utc)
    ttl = timedelta(days=get_settings().trusted_device_ttl_days)
    token = generate_token()
    device = TrustedDevice(
        user_id=user_id,
        token_hash=hash_token(token),
        device_name=_device_label(request),
        user_agent=request.headers.get("user-agent", "")[:300],
        ip=request.client.host if request.client else "",
        expires_at=now + ttl,
    )
    db.add(device)
    db.commit()
    set_trusted_device_cookie(response, token, ttl)
    return device


def find_valid(db: Session, user_id: uuid.UUID, raw_token: str | None) -> TrustedDevice | None:
    """返回仍有效（未撤销、未过期）的可信设备；命中时刷新 last_used_at。"""
    if not raw_token:
        return None
    now = datetime.now(timezone.utc)
    device = db.scalar(
        select(TrustedDevice).where(
            TrustedDevice.token_hash == hash_token(raw_token),
            TrustedDevice.user_id == user_id,
            TrustedDevice.revoked_at.is_(None),
        )
    )
    if device is None or _as_utc(device.expires_at) < now:
        return None
    device.last_used_at = now
    db.commit()
    return device


def revoke_one(db: Session, user_id: uuid.UUID, device_id: uuid.UUID) -> TrustedDevice | None:
    device = db.get(TrustedDevice, device_id)
    if device is None or device.user_id != user_id or device.revoked_at is not None:
        return None
    device.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return device


def revoke_all(db: Session, user_id: uuid.UUID) -> int:
    result = db.execute(
        update(TrustedDevice)
        .where(
            TrustedDevice.user_id == user_id,
            TrustedDevice.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount or 0
