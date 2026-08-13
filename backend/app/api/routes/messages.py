import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.services.notifications import render_template

router = APIRouter(prefix="/api/v1/me", tags=["messages"])


def _serialize(
    recipient: NotificationRecipient, notification: Notification, user: User
) -> dict:
    return {
        "id": str(recipient.id),
        "title": render_template(notification.title, user),
        "body": render_template(notification.body, user),
        "sent_at": notification.created_at,
        "read": recipient.read_at is not None,
    }


@router.get("/messages", response_model=dict)
def list_messages(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    base = (
        select(NotificationRecipient, Notification)
        .join(
            Notification,
            NotificationRecipient.notification_id == Notification.id,
        )
        .where(
            NotificationRecipient.user_id == user.id,
            Notification.recalled_at.is_(None),
        )
    )
    total = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .join(
                Notification,
                NotificationRecipient.notification_id == Notification.id,
            )
            .where(
                NotificationRecipient.user_id == user.id,
                Notification.recalled_at.is_(None),
            )
        )
        or 0
    )
    unread = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .join(
                Notification,
                NotificationRecipient.notification_id == Notification.id,
            )
            .where(
                NotificationRecipient.user_id == user.id,
                NotificationRecipient.read_at.is_(None),
                Notification.recalled_at.is_(None),
            )
        )
        or 0
    )
    rows = db.execute(
        base.order_by(NotificationRecipient.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            _serialize(recipient, notification, user)
            for recipient, notification in rows
        ],
        "total": total,
        "unread": unread,
    }


@router.get("/messages/unread-count", response_model=dict)
def unread_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    count = (
        db.scalar(
            select(func.count())
            .select_from(NotificationRecipient)
            .join(
                Notification,
                NotificationRecipient.notification_id == Notification.id,
            )
            .where(
                NotificationRecipient.user_id == user.id,
                NotificationRecipient.read_at.is_(None),
                Notification.recalled_at.is_(None),
            )
        )
        or 0
    )
    return {"unread": count}


def _get_own(db: Session, user: User, message_id: uuid.UUID):
    recipient = db.scalar(
        select(NotificationRecipient).where(
            NotificationRecipient.id == message_id,
            NotificationRecipient.user_id == user.id,
        )
    )
    if recipient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "消息不存在")
    return recipient


@router.post(
    "/messages/{message_id}/read", status_code=status.HTTP_204_NO_CONTENT
)
def mark_read(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    recipient = _get_own(db, user, message_id)
    if recipient.read_at is None:
        recipient.read_at = datetime.now(timezone.utc)
        db.commit()


@router.post("/messages/read-all", response_model=dict)
def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    result = db.execute(
        update(NotificationRecipient)
        .where(
            NotificationRecipient.user_id == user.id,
            NotificationRecipient.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"updated": result.rowcount or 0}


@router.delete(
    "/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_message(
    message_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    recipient = _get_own(db, user, message_id)
    db.delete(recipient)
    db.commit()
