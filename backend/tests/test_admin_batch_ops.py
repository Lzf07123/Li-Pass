import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole, UserStatus
from app.security.passwords import hash_password
from app.services.rate_limit import MemoryRateLimiter


def _login_admin(client, db_session) -> User:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    return admin


def _make_user(db_session, email: str, role: UserRole = UserRole.user) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=email.split("@")[0],
        role=role,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_batch_update_status_and_role(client, db_session) -> None:
    admin = _login_admin(client, db_session)
    bob = _make_user(db_session, "bob@example.com")
    carol = _make_user(db_session, "carol@example.com")

    response = client.patch(
        "/api/v1/admin/users/batch",
        json={
            "user_ids": [str(bob.id), str(carol.id)],
            "status": "disabled",
            "role": "admin",
            "current_password": "password123",
        },
    )
    assert response.status_code == 200
    updated = response.json()["updated"]
    assert len(updated) == 2
    assert {item["email"] for item in updated} == {
        "bob@example.com",
        "carol@example.com",
    }
    assert all(item["status"] == "disabled" for item in updated)
    assert all(item["role"] == "admin" for item in updated)

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_batch_update_user")
    ).all()
    assert len(logs) == 1
    assert logs[0].actor_id == str(admin.id)
    assert logs[0].detail["status"] == "disabled"


def test_batch_update_requires_field_and_existing_users(client, db_session) -> None:
    _login_admin(client, db_session)
    bob = _make_user(db_session, "bob@example.com")

    assert (
        client.patch(
            "/api/v1/admin/users/batch",
            json={"user_ids": [str(bob.id)]},
        ).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/v1/admin/users/batch",
            json={
                "user_ids": [str(uuid.uuid4())],
                "status": "disabled",
            },
        ).status_code
        == 404
    )


def test_batch_update_protects_self(client, db_session) -> None:
    admin = _login_admin(client, db_session)
    assert (
        client.patch(
            "/api/v1/admin/users/batch",
            json={"user_ids": [str(admin.id)], "status": "disabled"},
        ).status_code
        == 400
    )
    assert (
        client.patch(
            "/api/v1/admin/users/batch",
            json={"user_ids": [str(admin.id)], "role": "user"},
        ).status_code
        == 400
    )


def test_batch_delete_requires_password_and_protections(
    client, captured_email, db_session, engine
) -> None:
    admin = _login_admin(client, db_session)
    bob = _make_user(db_session, "bob@example.com")
    carol = _make_user(db_session, "carol@example.com")
    other_admin = _make_user(db_session, "other@example.com", role=UserRole.admin)

    wrong = client.post(
        "/api/v1/admin/users/batch/delete",
        json={
            "user_ids": [str(bob.id), str(carol.id)],
            "current_password": "wrong",
        },
    )
    assert wrong.status_code == 400

    self_delete = client.post(
        "/api/v1/admin/users/batch/delete",
        json={
            "user_ids": [str(admin.id)],
            "current_password": "password123",
        },
    )
    assert self_delete.status_code == 400

    admin_delete = client.post(
        "/api/v1/admin/users/batch/delete",
        json={
            "user_ids": [str(other_admin.id)],
            "current_password": "password123",
        },
    )
    assert admin_delete.status_code == 403

    ok = client.post(
        "/api/v1/admin/users/batch/delete",
        json={
            "user_ids": [str(bob.id), str(carol.id)],
            "current_password": "password123",
        },
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["message"] == "已删除 2 个账号"
    assert {item["email"] for item in body["deleted"]} == {
        "bob@example.com",
        "carol@example.com",
    }
    deleted_mails = [
        m for m in captured_email.messages if m[0] == "account_deleted"
    ]
    assert {m[1] for m in deleted_mails} == {
        "bob@example.com",
        "carol@example.com",
    }
    with Session(engine) as check:
        assert check.get(User, bob.id) is None
        assert check.get(User, carol.id) is None

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_batch_delete_user")
    ).all()
    assert len(logs) == 1
    assert logs[0].actor_id == str(admin.id)


def test_batch_invite_sends_and_skips_registered(client, captured_email, db_session) -> None:
    _login_admin(client, db_session)
    _make_user(db_session, "taken@example.com")

    response = client.post(
        "/api/v1/admin/users/batch/invite",
        json={
            "emails": [
                "a@example.com",
                "b@example.com",
                "taken@example.com",
            ]
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["invited"] == ["a@example.com", "b@example.com"]
    assert body["skipped"] == [
        {"email": "taken@example.com", "reason": "already_registered"}
    ]
    assert body["failed"] == []
    assert len([m for m in captured_email.messages if m[0] == "invite"]) == 2
    assert len(db_session.scalars(select(AccountInvite)).all()) == 2

    # 重复批量邀请：已有未消费邀请的邮箱直接跳过，不重复发信。
    again = client.post(
        "/api/v1/admin/users/batch/invite",
        json={"emails": ["a@example.com", "c@example.com"]},
    )
    assert again.status_code == 200
    assert again.json()["skipped"] == [
        {"email": "a@example.com", "reason": "already_invited"}
    ]
    assert again.json()["invited"] == ["c@example.com"]
    assert len([m for m in captured_email.messages if m[0] == "invite"]) == 3


def test_batch_invite_isolates_email_failure(client, captured_email, db_session, monkeypatch) -> None:
    _login_admin(client, db_session)

    class BrokenEmail:
        def send_invite(self, to, link):
            if to == "fail@example.com":
                raise RuntimeError("smtp down")
            captured_email.messages.append(("invite", to, link))

        def send_invite_batch(self, items):
            results = []
            for to, link in items:
                try:
                    self.send_invite(to, link)
                    results.append(None)
                except Exception as exc:
                    results.append(exc)
            return results

    monkeypatch.setattr(
        "app.api.routes.admin_users.get_email_service", lambda: BrokenEmail()
    )
    response = client.post(
        "/api/v1/admin/users/batch/invite",
        json={"emails": ["ok@example.com", "fail@example.com"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["invited"] == ["ok@example.com"]
    assert body["failed"] == [
        {"email": "fail@example.com", "reason": "邮件发送失败"}
    ]
    invites = db_session.scalars(select(AccountInvite)).all()
    assert [invite.email for invite in invites] == ["ok@example.com"]


def test_rate_limiter_supports_increment() -> None:
    limiter = MemoryRateLimiter()
    assert limiter.hit("admin_invite", "127.0.0.1", 60, increment=5) == 5
    assert limiter.hit("admin_invite", "127.0.0.1", 60) == 6
