import logging
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import get_settings
from app.core.db import get_db
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User, UserStatus
from app.services.audit import log_audit, log_rate_limit_rejected_once
from app.services.email import get_email_service
from app.services.rate_limit import get_rate_limiter

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin-notifications"],
    dependencies=[Depends(get_current_admin)],
)

_PLACEHOLDER_RE = re.compile(r"\{([^{}]+)\}")
_ALLOWED_PLACEHOLDERS = frozenset({"nickname", "email"})


class AdminNotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)
    in_site: bool = True
    email: bool = False
    user_ids: list[uuid.UUID] | None = Field(
        default=None, min_length=1, max_length=500
    )


def _unknown_placeholders(*texts: str) -> list[str]:
    tokens: set[str] = set()
    for text in texts:
        tokens.update(_PLACEHOLDER_RE.findall(text))
    return sorted(tokens - _ALLOWED_PLACEHOLDERS)


def _render(template: str, user: User) -> str:
    return (
        template.replace("{nickname}", user.nickname or "")
        .replace("{email}", user.email)
    )


@router.post("/notifications", response_model=dict)
def send_notification(
    payload: AdminNotificationCreate,
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    if not payload.in_site and not payload.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "至少选择一种发送渠道")
    invalid = _unknown_placeholders(payload.title, payload.body)
    if invalid:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "不支持的占位符："
            + ", ".join(f"{{{token}}}" for token in invalid)
            + "，仅支持 {nickname}、{email}",
        )

    settings = get_settings()
    ip = request.client.host if request.client else ""
    batch_count = get_rate_limiter().hit(
        "admin_notification",
        ip,
        settings.admin_notification_rate_window_seconds,
    )
    if batch_count > settings.admin_notification_rate_limit:
        log_rate_limit_rejected_once(
            db,
            "admin_send_notification",
            batch_count,
            settings.admin_notification_rate_limit,
            actor_type="admin",
            actor_id=str(actor.id),
            ip=ip,
            detail={"action": "admin_send_notification", "reason": "rate_limit"},
        )
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "发送通知过于频繁，请稍后再试"
        )

    skipped = 0
    if payload.user_ids is not None:
        ids = list(dict.fromkeys(payload.user_ids))
        if len(ids) > settings.notification_max_recipients:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"单次最多发送给 {settings.notification_max_recipients} 个用户",
            )
        users = db.scalars(
            select(User).where(
                User.id.in_(ids),
                User.status == UserStatus.active,
            )
        ).all()
        recipients = users
        skipped = len(ids) - len(recipients)
        if not recipients:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "没有可接收通知的用户"
            )
    else:
        recipient_count = (
            db.scalar(
                select(func.count())
                .select_from(User)
                .where(User.status == UserStatus.active)
            )
            or 0
        )
        if recipient_count == 0:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "没有可接收通知的用户"
            )
        if recipient_count > settings.notification_max_recipients:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"用户总数超过单次上限（{settings.notification_max_recipients}），"
                "请指定用户分批发送",
            )
        recipients = db.scalars(
            select(User).where(User.status == UserStatus.active)
        ).all()

    notification = Notification(
        title=payload.title,
        body=payload.body,
        in_site=payload.in_site,
        email=payload.email,
        sender_id=actor.id,
        recipient_count=len(recipients),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    if payload.in_site:
        for user in recipients:
            db.add(
                NotificationRecipient(
                    notification_id=notification.id, user_id=user.id
                )
            )
        db.commit()

    email_sent = 0
    email_failed = 0
    failed_emails: list[str] = []
    if payload.email:
        targets = [user for user in recipients if user.email_notifications]
        items = [
            (
                user.email,
                _render(payload.title, user),
                _render(payload.body, user),
            )
            for user in targets
        ]
        results = get_email_service().send_custom_notification_batch(items)
        for user, result in zip(targets, results):
            if result is None:
                email_sent += 1
            else:
                email_failed += 1
                failed_emails.append(user.email)
                logger.error(
                    "通知邮件发送失败：%s error=%s", user.email, result
                )
        notification.email_sent = email_sent
        notification.email_failed = email_failed
        db.commit()

    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_send_notification",
        category="admin_notification",
        target_type="notification",
        target_id=str(notification.id),
        ip=ip,
        user_agent=request.headers.get("user-agent"),
        detail={
            "title": payload.title,
            "in_site": payload.in_site,
            "email": payload.email,
            "recipient_count": len(recipients),
            "skipped": skipped,
            "email_sent": email_sent,
            "email_failed": email_failed,
            "failed_emails": failed_emails[:20],
        },
    )
    return {
        "id": str(notification.id),
        "recipient_count": len(recipients),
        "skipped": skipped,
        "email_sent": email_sent,
        "email_failed": email_failed,
    }


@router.get("/notifications", response_model=dict)
def list_notifications(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    base = select(Notification, User).join(
        User, Notification.sender_id == User.id, isouter=True
    )
    total = (
        db.scalar(select(func.count()).select_from(Notification)) or 0
    )
    rows = db.execute(
        base.order_by(Notification.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "id": str(notification.id),
                "title": notification.title,
                "in_site": notification.in_site,
                "email": notification.email,
                "recipient_count": notification.recipient_count,
                "email_sent": notification.email_sent,
                "email_failed": notification.email_failed,
                "created_at": notification.created_at,
                "sender_email": sender.email if sender else None,
                "sender_nickname": sender.nickname if sender else None,
            }
            for notification, sender in rows
        ],
        "total": total,
    }
