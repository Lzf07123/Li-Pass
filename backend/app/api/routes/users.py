import logging
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.models.otp import OtpPurpose
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.models.user_consent import UserConsent
from app.schemas.auth import (
    AppOut,
    PasswordConfirm,
    PasswordChange,
    PhoneBind,
    ProfileUpdate,
    SessionOut,
    StepUpVerifyRequest,
    UserOut,
    serialize_user,
)
from app.security.passwords import hash_password
from app.services.account_deletion import delete_user_account
from app.services.device_info import describe_session_device
from app.services.avatar_cleanup import delete_avatar_file
from app.services.audit import log_audit, mask_phone
from app.services.email import get_email_service
from app.services.federated_logout import (
    collect_logout_targets,
    collect_logout_targets_for_user_client,
    dispatch_backchannel_logout,
)
from app.services.otps import create_otp, verify_otp
from app.services.rate_limit import get_rate_limiter
from app.services.stepup import authorize_stepup, stepup_status

router = APIRouter(prefix="/api/v1", tags=["users"])
logger = logging.getLogger(__name__)


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


@router.get("/me/step-up")
def stepup_status_endpoint(
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """当前会话的 step-up 复核窗口状态。"""
    session = get_current_session(request, db)
    return stepup_status(session)


@router.post("/me/step-up")
def stepup_verify(
    payload: StepUpVerifyRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict:
    """在已登录会话上复核密码：成功后开启 30 分钟敏感操作免复核窗口。"""
    session = get_current_session(request, db)
    user = get_current_user(request, db)
    authorize_stepup(request, db, user, session, payload.password)
    result = stepup_status(session)
    return {**result, "message": "身份复核成功"}


@router.put("/me", response_model=UserOut)
def update_profile(
    payload: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    old_avatar = user.avatar_url
    if payload.nickname is not None:
        user.nickname = payload.nickname
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    if payload.email_notifications is not None:
        user.email_notifications = payload.email_notifications
    db.commit()
    log_audit(
        db,
        "user",
        str(user.id),
        "profile_update",
        category="user",
        target_type="user",
        target_id=str(user.id),
        detail={
            "nickname_changed": payload.nickname is not None,
            "email_notifications_changed": payload.email_notifications
            is not None,
        },
    )
    # 头像地址被替换/改为外链/清空时，旧的本地上传文件不再被引用，立即删除。
    if old_avatar and old_avatar != user.avatar_url:
        upload_dir = Path(get_settings().avatar_upload_dir)
        owner_dir = upload_dir / str(user.id)
        try:
            delete_avatar_file(upload_dir, old_avatar, owner_dir=owner_dir)
        except OSError:
            logger.warning("清理旧头像失败：%s", old_avatar, exc_info=True)
    return serialize_user(user)


@router.post("/me/password")
def change_password(
    payload: PasswordChange,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    user.password_hash = hash_password(payload.new_password)
    current = session
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
    log_audit(db, "user", str(user.id), "password_change", category="user")
    return {"message": "密码已修改，其他会话已退出"}


@router.post("/me/delete")
def delete_own_account(
    payload: PasswordConfirm,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # 注销账号不可逆：必须本人复核（密码或 30 分钟窗口），
    # 防止会话被窃取后静默注销。
    session = get_current_session(request, db)
    authorize_stepup(request, db, user, session, payload.current_password)
    if user.role == UserRole.admin:
        admin_count = db.scalar(
            select(func.count()).select_from(User).where(User.role == UserRole.admin)
        )
        if admin_count is not None and admin_count <= 1:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "最后一位管理员不能注销账号"
            )

    user_id = str(user.id)
    user_email = user.email
    user_nickname = user.nickname
    delete_user_account(db, user)
    log_audit(
        db,
        "user",
        user_id,
        "user_delete_self",
        category="user",
        target_type="user",
        target_id=user_id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"email": user_email},
    )
    try:
        get_email_service().send_account_deleted(user_email, user_nickname)
    except Exception:
        logger.exception("账号注销通知邮件发送失败：%s", user_email)
    return {"message": "账号已注销"}


@router.post("/me/phone/bind/send")
def send_phone_bind_code(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    send_count = get_rate_limiter().hit(
        "otp_send", user.email, settings.otp_send_window_seconds
    )
    if send_count > settings.otp_send_limit:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"验证码发送过于频繁，请在 "
            f"{settings.otp_send_window_seconds // 60} 分钟后重试",
        )
    code = create_otp(db, OtpPurpose.bind_phone, user.email)
    try:
        get_email_service().send_verification(user.email, code)
        db.commit()
        log_audit(
            db,
            "user",
            str(user.id),
            "phone_bind_send",
            category="user",
            target_type="user",
            target_id=str(user.id),
        )
    except Exception:
        db.rollback()
        get_rate_limiter().decrement("otp_send", user.email)
        logger.exception("绑定邮箱验证码发送失败：%s", user.email)
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            "邮件发送失败，请稍后重试",
        )
    return {"message": "验证码已发送至绑定邮箱"}


@router.post("/me/phone/bind", response_model=UserOut)
def bind_phone(
    payload: PhoneBind,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if not verify_otp(db, OtpPurpose.bind_phone, user.email, payload.code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "验证码无效或已过期")
    user.phone = payload.phone
    user.phone_verified_at = datetime.now(timezone.utc)
    db.commit()
    log_audit(
        db,
        "user",
        str(user.id),
        "phone_bind",
        category="user",
        target_type="user",
        target_id=str(user.id),
        detail={"phone": mask_phone(payload.phone)},
    )
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
            "device_name": describe_session_device(s.device_name, s.user_agent),
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
    background_tasks: BackgroundTasks,
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
    targets = collect_logout_targets(db, [session.id])
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    log_audit(
        db,
        "user",
        str(user.id),
        "session_revoke",
        category="user",
        target_type="session",
        target_id=str(session.id),
    )


@router.post("/sessions/revoke-all", response_model=dict)
def revoke_all_sessions(
    request: Request,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """退出除当前会话外的全部登录设备；当前会话不受影响。"""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    idle_cutoff = now - timedelta(days=settings.session_idle_days)
    # 先清理本用户过期/空闲超时的“僵尸”会话，与列表口径一致，
    # 避免把它们计入退出数量；只作用于当前用户，不影响他人。
    db.execute(
        update(SessionModel)
        .where(
            SessionModel.revoked_at.is_(None),
            SessionModel.user_id == user.id,
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
            SessionModel.user_id == user.id,
            SessionModel.id != current.id,
        )
    ).all()
    result = db.execute(
        update(SessionModel)
        .where(
            SessionModel.revoked_at.is_(None),
            SessionModel.user_id == user.id,
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
    log_audit(
        db,
        "user",
        str(user.id),
        "session_revoke_all",
        category="user",
        target_type="session",
        target_id=None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"count": count},
    )
    return {"revoked": count}


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
    # 一次查询取回所有相关黑名单，替代“每个应用一次 find_block”的 N+1 查询。
    blocks = db.scalars(
        select(ClientUserBlock).where(
            ClientUserBlock.client_id.in_(client_ids),
            or_(
                ClientUserBlock.user_id == user.id,
                ClientUserBlock.email == user.email,
            ),
        )
    ).all()
    blocked_client_ids = {block.client_id for block in blocks}
    result = []
    for client in clients:
        if client.id in blocked_client_ids:
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
    background_tasks: BackgroundTasks,
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
    targets = collect_logout_targets_for_user_client(db, user.id, client.id)
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    log_audit(
        db,
        "user",
        str(user.id),
        "app_consent_revoke",
        category="consent",
        target_type="oauth_client",
        target_id=str(client.id),
    )
    return {"logout_uri": client.logout_uri}


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if file.content_type not in _AVATAR_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅支持 JPG/PNG/GIF/WebP 图片")
    max_bytes = settings.avatar_max_size_mb * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"头像大小不能超过 {settings.avatar_max_size_mb} MB",
        )
    # 只读取上限 + 1 字节，避免大文件整体读入内存造成 DoS。
    content = await file.read(max_bytes + 1)
    ext = _avatar_ext(content)
    if ext is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片文件内容无效")
    if len(content) > max_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"头像大小不能超过 {settings.avatar_max_size_mb} MB",
        )

    upload_dir = Path(settings.avatar_upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    user_dir = upload_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    (user_dir / filename).write_bytes(content)

    old = user.avatar_url
    if old and old.startswith("/uploads/avatars/"):
        try:
            delete_avatar_file(upload_dir, old, owner_dir=user_dir)
        except OSError:
            logger.warning("清理旧头像失败：%s", old, exc_info=True)

    user.avatar_url = f"/uploads/avatars/{user.id}/{filename}"
    db.commit()
    log_audit(
        db,
        "user",
        str(user.id),
        "avatar_upload",
        category="user",
        target_type="user",
        target_id=str(user.id),
    )
    return serialize_user(user)
