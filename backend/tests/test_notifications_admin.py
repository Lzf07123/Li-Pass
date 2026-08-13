import uuid

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User, UserStatus
from app.security.passwords import hash_password
from tests.test_admin_sessions import login_admin


def make_user(db_session, email, nickname=None, **overrides) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=nickname or email.split("@")[0],
        **overrides,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_send_in_site_notification_to_all_users(client, db_session) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    bob = make_user(db_session, "bob@example.com", "Bob")

    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "维护",
            "body": "您好，{nickname}",
            "in_site": True,
            "email": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_count"] == 3  # alice + bob + 管理员
    assert data["email_sent"] == 0
    assert data["email_failed"] == 0

    notification = db_session.get(Notification, uuid.UUID(data["id"]))
    assert notification is not None
    recipients = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.notification_id == notification.id
        )
    ).all()
    ids = {recipient.user_id for recipient in recipients}
    assert alice.id in ids and bob.id in ids
    assert all(recipient.read_at is None for recipient in recipients)

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "admin_send_notification")
    )
    assert audit is not None
    assert audit.category == "admin_notification"


def test_send_email_to_specific_users_renders_placeholders(
    client, db_session, captured_email
) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    bob = make_user(
        db_session, "bob@example.com", "Bob", email_notifications=False
    )

    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "你好 {nickname}",
            "body": "邮箱：{email}",
            "in_site": False,
            "email": True,
            "user_ids": [str(alice.id), str(bob.id)],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_count"] == 2
    assert data["skipped"] == 0
    assert data["email_sent"] == 1  # bob 关闭邮件通知，被跳过
    assert data["email_failed"] == 0

    custom = [m for m in captured_email.messages if m[0] == "custom_notification"]
    assert len(custom) == 1
    assert custom[0][1] == "alice@example.com"
    assert "Alice" in custom[0][2]
    assert "alice@example.com" in custom[0][2]

    # 仅邮件渠道不产生站内信收件行
    recipients = db_session.scalars(select(NotificationRecipient)).all()
    assert recipients == []


def test_send_notification_skips_missing_and_disabled_users(
    client, db_session
) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    disabled = make_user(
        db_session,
        "disabled@example.com",
        "Disabled",
        status=UserStatus.disabled,
    )
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "t",
            "body": "b",
            "in_site": True,
            "email": False,
            "user_ids": [str(alice.id), str(disabled.id), str(uuid.uuid4())],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["recipient_count"] == 1
    assert data["skipped"] == 2


def test_send_notification_rejects_when_no_valid_recipients(
    client, db_session
) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "t",
            "body": "b",
            "in_site": True,
            "email": False,
            "user_ids": [str(uuid.uuid4())],
        },
    )
    assert response.status_code == 400


def test_send_notification_requires_a_channel(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": False, "email": False},
    )
    assert response.status_code == 400


def test_send_notification_rejects_unknown_placeholders(
    client, db_session
) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "你好 {name}",
            "body": "正文 {nickname}",
            "in_site": True,
            "email": False,
        },
    )
    assert response.status_code == 400
    assert "{name}" in response.json()["detail"]
    assert "仅支持 {nickname}、{email}" in response.json()["detail"]


def test_send_notification_allows_literal_braces(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "公告",
            "body": "价格为 100 { 元（示例）",
            "in_site": True,
            "email": False,
        },
    )
    assert response.status_code == 200


def test_list_notifications_history(client, db_session) -> None:
    login_admin(client, db_session)
    client.post(
        "/api/v1/admin/notifications",
        json={"title": "第一条", "body": "b", "in_site": True, "email": False},
    )
    client.post(
        "/api/v1/admin/notifications",
        json={"title": "第二条", "body": "b", "in_site": True, "email": False},
    )

    response = client.get("/api/v1/admin/notifications")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert {item["title"] for item in data["items"]} == {"第一条", "第二条"}
    item = data["items"][0]
    assert item["in_site"] is True
    assert item["email"] is False
    assert item["sender_email"] == "admin@example.com"
    assert item["recipient_count"] >= 1


def test_recall_in_site_notification_removes_from_inbox(
    client, db_session
) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    response = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "公告",
            "body": "你好 {nickname}",
            "in_site": True,
            "email": False,
            "user_ids": [str(alice.id)],
        },
    )
    notification_id = response.json()["id"]

    client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert client.get("/api/v1/me/messages").json()["total"] == 1

    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    recall = client.post(
        f"/api/v1/admin/notifications/{notification_id}/recall"
    )
    assert recall.status_code == 200
    assert recall.json()["recalled"] == 1

    client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert client.get("/api/v1/me/messages").json()["total"] == 0
    assert client.get("/api/v1/me/messages/unread-count").json() == {
        "unread": 0
    }

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "admin_recall_notification"
        )
    )
    assert audit is not None


def test_recall_is_idempotent_and_rejects_email_only(
    client, db_session
) -> None:
    login_admin(client, db_session)
    alice = make_user(db_session, "alice@example.com", "Alice")
    in_site = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "公告",
            "body": "b",
            "in_site": True,
            "email": False,
            "user_ids": [str(alice.id)],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/admin/notifications/{in_site['id']}/recall"
        ).status_code
        == 200
    )
    # 重复撤回幂等
    assert (
        client.post(
            f"/api/v1/admin/notifications/{in_site['id']}/recall"
        ).status_code
        == 200
    )

    email_only = client.post(
        "/api/v1/admin/notifications",
        json={
            "title": "邮件",
            "body": "b",
            "in_site": False,
            "email": True,
            "user_ids": [str(alice.id)],
        },
    ).json()
    assert (
        client.post(
            f"/api/v1/admin/notifications/{email_only['id']}/recall"
        ).status_code
        == 400
    )

    history = client.get("/api/v1/admin/notifications").json()["items"]
    recalled = next(item for item in history if item["id"] == in_site["id"])
    assert recalled["recalled_at"] is not None
    not_recalled = next(item for item in history if item["id"] == email_only["id"])
    assert not_recalled["recalled_at"] is None


def test_send_notification_hits_rate_limit(client, db_session) -> None:
    login_admin(client, db_session)
    from app.services.rate_limit import get_rate_limiter

    limiter = get_rate_limiter()
    limiter.hit("admin_notification", "testclient", 3600, increment=21)
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": True, "email": False},
    )
    assert response.status_code == 429


def test_non_admin_cannot_send_notification(
    client, captured_email, db_session
) -> None:
    from tests.helpers import register_and_login

    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/admin/notifications",
        json={"title": "t", "body": "b", "in_site": True, "email": False},
    )
    assert response.status_code == 403
    assert (
        client.post(
            f"/api/v1/admin/notifications/{uuid.uuid4()}/recall"
        ).status_code
        == 403
    )
