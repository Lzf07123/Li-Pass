from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_token, hash_token
from tests.helpers import (
    critical_stepup_payload,
    login_with_email_2fa,
    register_and_login,
)


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


def _token_from_link(link: str) -> str:
    assert "token=" in link
    return link.split("token=", 1)[1]


def test_admin_create_user_directly(client, captured_email, db_session) -> None:
    admin = _login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/users",
        json={
            "email": "newbie@example.com",
            "nickname": "Newbie",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "newbie@example.com"
    assert body["role"] == "user"
    assert body["status"] == "active"

    # 重复创建被拒绝
    assert (
        client.post(
            "/api/v1/admin/users",
            json={
                "email": "newbie@example.com",
                "nickname": "Newbie2",
                "password": "password123",
            },
        ).status_code
        == 409
    )

    # 管理员代建账号视为已验证邮箱，强制 2FA 下登录需完成邮箱验证码。
    assert (
        login_with_email_2fa(
            client,
            captured_email,
            "newbie@example.com",
            "password123",
        ).status_code
        == 200
    )

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_create_user")
    ).all()
    assert len(logs) == 1
    assert logs[0].actor_id == str(admin.id)
    assert logs[0].detail["email"] == "newbie@example.com"


def test_admin_invite_and_invitee_registers(
    client, captured_email, db_session
) -> None:
    admin = _login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/users/invite",
        json={"email": "invitee@example.com", "nickname": "Invitee"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "邀请邮件已发送"

    invite_messages = [m for m in captured_email.messages if m[0] == "invite"]
    assert len(invite_messages) == 1
    link = invite_messages[0][2]
    token = _token_from_link(link)

    # 邀请令牌只保存哈希
    stored = db_session.scalar(select(AccountInvite))
    assert stored is not None
    assert token not in stored.token_hash
    assert stored.created_by == admin.id
    assert stored.nickname == "Invitee"

    response = client.post(
        "/api/v1/auth/invite/register",
        json={
            "token": token,
            "nickname": "My Name",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    user = db_session.scalar(
        select(User).where(User.email == "invitee@example.com")
    )
    assert user is not None
    assert user.nickname == "My Name"
    assert user.email_verified_at is not None
    assert verify_password("password123", user.password_hash)

    # 令牌一次性使用
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={
                "token": token,
                "nickname": "Again",
                "password": "password123",
            },
        ).status_code
        == 400
    )

    actions = [
        log.action
        for log in db_session.scalars(
            select(AuditLog).where(
                AuditLog.action.in_(
                    ["admin_invite_user", "user_register_by_invite"]
                )
            )
        ).all()
    ]
    assert "admin_invite_user" in actions
    assert "user_register_by_invite" in actions


def test_pending_invites_visible_in_admin_user_list(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "invitee@example.com", "nickname": "Invitee"},
    )

    rows = client.get("/api/v1/admin/users").json()
    invite = next(
        (row for row in rows if row["email"] == "invitee@example.com"), None
    )
    assert invite is not None
    assert invite["kind"] == "invite"
    assert invite["status"] == "invited"
    assert invite["nickname"] == "Invitee"
    assert invite["expires_at"] is not None

    # 按邮箱/昵称搜索同样能搜到待注册邀请
    searched = client.get(
        "/api/v1/admin/users", params={"q": "invitee"}
    ).json()
    assert [row["email"] for row in searched] == ["invitee@example.com"]
    assert searched[0]["kind"] == "invite"
    assert searched[0]["status"] == "invited"

    # 状态筛选能定位待注册邀请；角色筛选只保留已注册用户
    invited = client.get(
        "/api/v1/admin/users", params={"status": "invited"}
    ).json()
    assert [row["email"] for row in invited] == ["invitee@example.com"]
    users_only = client.get(
        "/api/v1/admin/users", params={"role": "user"}
    ).json()
    assert all(row["kind"] == "user" for row in users_only)

    # 受邀者完成注册后，邀请行消失，用户行以正常状态出现
    invite_messages = [m for m in captured_email.messages if m[0] == "invite"]
    token = _token_from_link(invite_messages[-1][2])
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={
                "token": token,
                "nickname": "My Name",
                "password": "password123",
            },
        ).status_code
        == 201
    )
    rows = client.get("/api/v1/admin/users").json()
    assert not any(
        row["email"] == "invitee@example.com" and row["kind"] == "invite"
        for row in rows
    )
    user_row = next(
        row for row in rows if row["email"] == "invitee@example.com"
    )
    assert user_row["kind"] == "user"
    assert user_row["status"] == "active"


def test_expired_invite_shows_expired_status(client, db_session) -> None:
    _login_admin(client, db_session)
    db_session.add(
        AccountInvite(
            email="expired@example.com",
            token_hash=hash_token(generate_token()),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
    )
    db_session.commit()

    rows = client.get("/api/v1/admin/users").json()
    expired = next(
        row for row in rows if row["email"] == "expired@example.com"
    )
    assert expired["kind"] == "invite"
    assert expired["status"] == "expired"


def test_admin_cancel_invite_revokes_link(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "cancel@example.com", "nickname": "Cancel"},
    )
    rows = client.get("/api/v1/admin/users").json()
    invite = next(row for row in rows if row["email"] == "cancel@example.com")
    assert invite["status"] == "invited"

    response = client.post(
        f"/api/v1/admin/users/invites/{invite['id']}/cancel"
    )
    assert response.status_code == 200

    rows = client.get("/api/v1/admin/users").json()
    invite = next(row for row in rows if row["email"] == "cancel@example.com")
    assert invite["status"] == "cancelled"

    invite_messages = [m for m in captured_email.messages if m[0] == "invite"]
    token = _token_from_link(invite_messages[-1][2])
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "X", "password": "password123"},
        ).status_code
        == 400
    )
    # 重复取消返回明确错误
    assert (
        client.post(
            f"/api/v1/admin/users/invites/{invite['id']}/cancel"
        ).status_code
        == 400
    )


def test_admin_resend_invite_rotates_token(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "resend@example.com", "nickname": "Resend"},
    )
    rows = client.get("/api/v1/admin/users").json()
    invite = next(row for row in rows if row["email"] == "resend@example.com")

    response = client.post(
        f"/api/v1/admin/users/invites/{invite['id']}/resend"
    )
    assert response.status_code == 200

    invite_messages = [m for m in captured_email.messages if m[0] == "invite"]
    assert len(invite_messages) == 2
    old_token = _token_from_link(invite_messages[0][2])
    new_token = _token_from_link(invite_messages[1][2])
    assert new_token != old_token

    # 旧链接失效，新链接可用
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": old_token, "nickname": "Old", "password": "password123"},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": new_token, "nickname": "New", "password": "password123"},
        ).status_code
        == 201
    )


def test_admin_resend_cancelled_invite_reuses_record(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "cancel-resend@example.com"},
    )
    rows = client.get("/api/v1/admin/users").json()
    invite = next(
        row
        for row in rows
        if row["email"] == "cancel-resend@example.com"
    )
    assert (
        client.post(
            f"/api/v1/admin/users/invites/{invite['id']}/cancel"
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/admin/users/invites/{invite['id']}/resend"
        ).status_code
        == 200
    )

    # 复用原记录：列表只保留一条记录，状态恢复为“待注册”
    rows = client.get("/api/v1/admin/users").json()
    invite_rows = [
        row
        for row in rows
        if row["email"] == "cancel-resend@example.com"
        and row["kind"] == "invite"
    ]
    assert len(invite_rows) == 1
    assert invite_rows[0]["status"] == "invited"
    assert len(db_session.scalars(select(AccountInvite)).all()) == 1

    token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "Again", "password": "password123"},
        ).status_code
        == 201
    )


def test_admin_resend_expired_invite_revives(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "expired-resend@example.com"},
    )
    stored = db_session.scalar(
        select(AccountInvite).where(
            AccountInvite.email == "expired-resend@example.com"
        )
    )
    stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    rows = client.get("/api/v1/admin/users").json()
    invite = next(
        row
        for row in rows
        if row["email"] == "expired-resend@example.com"
    )
    assert invite["status"] == "expired"

    response = client.post(
        f"/api/v1/admin/users/invites/{invite['id']}/resend"
    )
    assert response.status_code == 200
    token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "Revived", "password": "password123"},
        ).status_code
        == 201
    )


def test_used_invite_restored_after_user_deleted_and_can_resend(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "deleted@example.com", "nickname": "Deleted"},
    )
    token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "My Name", "password": "password123"},
        ).status_code
        == 201
    )
    user = db_session.scalar(
        select(User).where(User.email == "deleted@example.com")
    )

    # 用户仍存在时，已使用邀请不重复展示
    rows = client.get("/api/v1/admin/users").json()
    assert not any(
        row["email"] == "deleted@example.com" and row["kind"] == "invite"
        for row in rows
    )

    # 注册后删除账号：邀请还原为“待注册”，可再次使用同一链接注册
    assert (
        client.post(
            f"/api/v1/admin/users/{user.id}/delete",
            json=critical_stepup_payload(
                client, captured_email, "admin@example.com"
            ),
        ).status_code
        == 200
    )
    rows = client.get("/api/v1/admin/users").json()
    restored = next(
        row
        for row in rows
        if row["email"] == "deleted@example.com" and row["kind"] == "invite"
    )
    assert restored["status"] == "invited"

    # 重发邀请：复用已还原的邀请，不生成重复记录
    before = len([m for m in captured_email.messages if m[0] == "invite"])
    response = client.post(
        f"/api/v1/admin/users/invites/{restored['id']}/resend"
    )
    assert response.status_code == 200
    assert (
        len([m for m in captured_email.messages if m[0] == "invite"])
        == before + 1
    )
    # 再次重发：复用已生成的有效邀请，不再产生重复行
    again = client.post(
        f"/api/v1/admin/users/invites/{restored['id']}/resend"
    )
    assert again.status_code == 200
    assert len(db_session.scalars(select(AccountInvite)).all()) == 1
    new_token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": new_token, "nickname": "Again", "password": "password123"},
        ).status_code
        == 201
    )
    assert len(db_session.scalars(select(AccountInvite)).all()) == 1


def test_resend_invite_rejected_when_email_registered(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "registered@example.com"},
    )
    token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "Registered", "password": "password123"},
        ).status_code
        == 201
    )
    stored = db_session.scalar(
        select(AccountInvite).where(
            AccountInvite.email == "registered@example.com"
        )
    )
    response = client.post(
        f"/api/v1/admin/users/invites/{stored.id}/resend"
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "该邮箱已注册，无需重发邀请"


def test_admin_delete_invite_removes_record(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "delete@example.com", "nickname": "Delete"},
    )
    rows = client.get("/api/v1/admin/users").json()
    invite = next(row for row in rows if row["email"] == "delete@example.com")

    response = client.post(
        f"/api/v1/admin/users/invites/{invite['id']}/delete"
    )
    assert response.status_code == 200
    assert response.json()["message"] == "邀请记录已删除"

    # 记录已删除，列表不再展示，原链接失效
    assert (
        db_session.scalar(
            select(AccountInvite).where(
                AccountInvite.email == "delete@example.com"
            )
        )
        is None
    )
    rows = client.get("/api/v1/admin/users").json()
    assert not any(
        row["email"] == "delete@example.com" and row["kind"] == "invite"
        for row in rows
    )
    token = _token_from_link(
        [m for m in captured_email.messages if m[0] == "invite"][-1][2]
    )
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": token, "nickname": "X", "password": "password123"},
        ).status_code
        == 400
    )

    # 重复删除返回 404；审计留痕
    assert (
        client.post(
            f"/api/v1/admin/users/invites/{invite['id']}/delete"
        ).status_code
        == 404
    )
    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_delete_invite")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["email"] == "delete@example.com"


def test_invite_register_rejects_bad_or_expired_tokens(
    client, captured_email, db_session
) -> None:
    _login_admin(client, db_session)
    client.post(
        "/api/v1/admin/users/invite",
        json={"email": "expired@example.com"},
    )
    db_session.scalar(select(AccountInvite)).expires_at = datetime.now(
        timezone.utc
    ) - timedelta(minutes=1)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/invite/register",
        json={
            "token": "x" * 43,
            "nickname": "Nobody",
            "password": "password123",
        },
    )
    assert response.status_code == 400


def test_invite_for_registered_email_conflicts(client, db_session) -> None:
    _login_admin(client, db_session)
    existing = User(
        email="taken@example.com",
        password_hash=hash_password("password123"),
        nickname="Taken",
    )
    db_session.add(existing)
    db_session.commit()

    assert (
        client.post(
            "/api/v1/admin/users/invite",
            json={"email": "taken@example.com"},
        ).status_code
        == 409
    )


def test_non_admin_cannot_create_or_invite(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/admin/users",
            json={
                "email": "x@example.com",
                "nickname": "X",
                "password": "password123",
            },
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/admin/users/invite",
            json={"email": "x@example.com"},
        ).status_code
        == 403
    )


def test_invite_send_failure_returns_502_and_rolls_back(
    client, db_session, monkeypatch
) -> None:
    _login_admin(client, db_session)

    class BrokenEmail:
        def send_invite(self, to, link):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(
        "app.api.routes.admin_users.get_email_service",
        lambda: BrokenEmail(),
    )
    response = client.post(
        "/api/v1/admin/users/invite",
        json={"email": "fail@example.com"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "邮件发送失败，请检查邮件服务配置"
    # 不留下未发送的“幽灵邀请”
    assert (
        db_session.scalar(
            select(AccountInvite).where(AccountInvite.email == "fail@example.com")
        )
        is None
    )
