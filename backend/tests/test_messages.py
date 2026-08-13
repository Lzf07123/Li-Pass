from sqlalchemy import select

from app.models.notification import Notification
from app.models.notification_recipient import NotificationRecipient
from app.models.user import User
from app.security.passwords import hash_password


def make_user(db_session, email) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=email.split("@")[0],
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def login(client, email) -> None:
    client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password123"},
    )


def send(
    db_session,
    sender: User,
    targets: list[User],
    title: str = "维护通知",
    body: str = "您好",
) -> Notification:
    notification = Notification(
        title=title,
        body=body,
        in_site=True,
        email=False,
        sender_id=sender.id,
        recipient_count=len(targets),
    )
    db_session.add(notification)
    db_session.commit()
    db_session.refresh(notification)
    for user in targets:
        db_session.add(
            NotificationRecipient(
                notification_id=notification.id, user_id=user.id
            )
        )
    db_session.commit()
    return notification


def test_messages_render_placeholders_per_recipient(
    client, db_session
) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    send(
        db_session,
        admin,
        [alice, bob],
        title="你好 {nickname}",
        body="邮箱：{email}",
    )
    login(client, "alice@example.com")

    data = client.get("/api/v1/me/messages").json()
    item = data["items"][0]
    assert item["title"] == "你好 alice"
    assert item["body"] == "邮箱：alice@example.com"
    assert "{nickname}" not in item["title"]
    assert "{email}" not in item["body"]


def test_list_messages_and_unread_count(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    send(db_session, admin, [alice, bob])
    login(client, "alice@example.com")

    data = client.get("/api/v1/me/messages").json()
    assert data["total"] == 1
    assert data["unread"] == 1
    assert data["items"][0]["title"] == "维护通知"
    assert data["items"][0]["read"] is False
    assert client.get("/api/v1/me/messages/unread-count").json() == {
        "unread": 1
    }


def test_mark_read_read_all_and_delete_own_messages(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    first = send(db_session, admin, [alice, bob])
    second = send(db_session, admin, [alice])
    login(client, "alice@example.com")

    mine = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == alice.id,
            NotificationRecipient.notification_id == first.id,
        )
    ).one()
    assert client.post(f"/api/v1/me/messages/{mine.id}/read").status_code == 204

    result = client.post("/api/v1/me/messages/read-all").json()
    assert result["updated"] == 1  # 第一条已读，剩第二条
    assert client.get("/api/v1/me/messages/unread-count").json() == {
        "unread": 0
    }

    other = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == alice.id,
            NotificationRecipient.notification_id == second.id,
        )
    ).one()
    assert client.delete(f"/api/v1/me/messages/{other.id}").status_code == 204
    assert client.get("/api/v1/me/messages").json()["total"] == 1


def test_cannot_touch_other_users_messages(client, db_session) -> None:
    admin = make_user(db_session, "admin@example.com")
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    send(db_session, admin, [alice, bob])
    login(client, "alice@example.com")
    bobs = db_session.scalars(
        select(NotificationRecipient).where(
            NotificationRecipient.user_id == bob.id
        )
    ).one()
    assert client.post(f"/api/v1/me/messages/{bobs.id}/read").status_code == 404
    assert client.delete(f"/api/v1/me/messages/{bobs.id}").status_code == 404


def test_requires_auth(client) -> None:
    assert client.get("/api/v1/me/messages").status_code == 401
