import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.session import Session as SessionModel
from app.models.user import User
from app.models.user_consent import UserConsent
from app.schemas.auth import (
    AppOut,
    PasswordChange,
    PhoneBind,
    ProfileUpdate,
    SessionOut,
    UserOut,
    serialize_user,
)
from app.security.passwords import hash_password, verify_password
from app.services.blocks import find_block
from app.services.audit import log_audit

router = APIRouter(prefix="/api/v1", tags=["users"])


_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def _avatar_ext(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"GIF8"):
        return ".gif"
    if content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return ".webp"
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> dict:
    return serialize_user(user)


@router.put("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    db.commit()
    return serialize_user(user)


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")
    user.password_hash = hash_password(payload.new_password)
    current = get_current_session(request, db)
    others = db.scalars(
        select(SessionModel).where(
            SessionModel.user_id == user.id,
            SessionModel.id != current.id,
            SessionModel.revoked_at.is_(None),
        )
    ).all()
    for session in others:
        session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(db, "user", str(user.id), "password_change")
    return {"message": "密码已修改，其他会话已退出"}


@router.post("/me/phone/bind", response_model=UserOut)
def bind_phone(
    payload: PhoneBind,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    user.phone = payload.phone
    user.phone_verified_at = datetime.now(timezone.utc)
    db.commit()
    return serialize_user(user)


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    current = get_current_session(request, db)
    sessions = db.scalars(
        select(SessionModel)
        .where(
            SessionModel.user_id == user.id,
            SessionModel.revoked_at.is_(None),
        )
        .order_by(SessionModel.created_at.desc())
    ).all()
    return [
        {
            "id": str(s.id),
            "device_name": s.device_name,
            "ip": s.ip,
            "user_agent": s.user_agent,
            "created_at": s.created_at,
            "last_used_at": s.last_used_at,
            "expires_at": s.expires_at,
            "current": s.id == current.id,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: uuid.UUID,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    session = db.get(SessionModel, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")
    current = get_current_session(request, db)
    if session.id == current.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "不能退出当前会话")
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/apps", response_model=list[AppOut])
def list_apps(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    consents = db.scalars(
        select(UserConsent).where(UserConsent.user_id == user.id)
    ).all()
    client_ids = [c.client_id for c in consents]
    if not client_ids:
        return []
    clients = db.scalars(
        select(OAuthClient).where(
            OAuthClient.id.in_(client_ids), OAuthClient.is_active.is_(True)
        )
    ).all()
    result = []
    for client in clients:
        if find_block(db, client.id, user) is not None:
            continue
        result.append(
            {
                "client_id": client.client_id,
                "name": client.name,
                "description": client.description,
                "logo_url": client.logo_url,
                "home_url": client.home_url,
            }
        )
    return result


@router.delete("/apps/{client_id}")
def revoke_app(
    client_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    client = db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id, OAuthClient.is_active.is_(True)
        )
    )
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    if consent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "尚未授权该应用")
    db.delete(consent)
    db.commit()
    log_audit(
        db,
        "user",
        str(user.id),
        "app_consent_revoke",
        target_type="oauth_client",
        target_id=str(client.id),
    )
    return {"logout_uri": client.logout_uri}


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if file.content_type not in _AVATAR_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 JPG/PNG/GIF/WebP 图片")
    content = await file.read()
    ext = _avatar_ext(content)
    if ext is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片文件内容无效")
    max_bytes = settings.avatar_max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"头像大小不能超过 {settings.avatar_max_size_mb} MB",
        )

    upload_dir = Path(settings.avatar_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (upload_dir / filename).write_bytes(content)

    old = user.avatar_url
    if old and old.startswith("/uploads/avatars/"):
        old_path = upload_dir / old.removeprefix("/uploads/avatars/")
        if old_path.is_file():
            old_path.unlink()

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    return serialize_user(user)
