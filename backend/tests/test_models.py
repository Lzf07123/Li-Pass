from datetime import datetime, timezone

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.otp import Otp, OtpPurpose
from app.models.session import Session
from app.models.user import User, UserRole, UserStatus
from app.security.passwords import hash_password


def test_create_user_session_otp(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="Alice")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert user.id is not None
    assert user.role == UserRole.user
    assert user.status == UserStatus.active

    session = Session(user_id=user.id, token_hash="abc", expires_at=user.created_at)
    otp = Otp(purpose=OtpPurpose.register, target=user.email, code_hash="def", expires_at=user.created_at)
    db_session.add_all([session, otp])
    db_session.commit()

    assert session.id is not None
    assert otp.id is not None


def test_notification_models_defaults(db_session) -> None:
    user = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    assert user.email_notifications is True

    notification = Notification(
        title="标题", body="正文", in_site=True, email=False, sender_id=user.id
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    assert notification.recipient_count == 0
    assert notification.email_sent == 0
    assert notification.email_failed == 0

    recipient = NotificationRecipient(
        notification_id=notification.id,
        user_id=user.id,
        read_at=datetime.now(timezone.utc),
    )
    db_session.add(recipient)
    db_session.commit()
    assert recipient.read_at is not None
