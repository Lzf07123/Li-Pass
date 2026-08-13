from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.authorization_code import AuthorizationCode
from app.models.client_user_block import ClientUserBlock
from app.models.otp import Otp, OtpPurpose
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.models.user_consent import UserConsent
from app.security.passwords import hash_password
from tests.helpers import create_client, register_and_login


def _now() -> datetime:
    return datetime.now(timezone.utc)


def test_self_service_delete_requires_password(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)

    response = client.post(
        "/api/v1/me/delete",
        json={"current_password": "wrong-password"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "当前密码错误"
    assert db_session.scalar(
        select(User).where(User.email == "a@example.com")
    ) is not None

    response = client.post(
        "/api/v1/me/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    deleted_mails = [
        m for m in captured_email.messages if m[0] == "account_deleted"
    ]
    assert len(deleted_mails) == 1
    assert deleted_mails[0][1] == "a@example.com"
    assert db_session.scalar(
        select(User).where(User.email == "a@example.com")
    ) is None
    # 旧会话随账号删除而失效
    assert client.get("/api/v1/me").status_code == 401
    # 邮箱可重新注册
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@example.com",
                "password": "password123",
                "nickname": "Alice2",
            },
        ).status_code
        == 201
    )


def test_self_service_delete_cleans_up_related_data(
    client, captured_email, db_session
) -> None:
    client_model = create_client(db_session)
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    db_session.add(
        UserConsent(user_id=user.id, client_id=client_model.id, scopes=["openid"])
    )
    db_session.add(
        RecoveryCode(
            user_id=user.id,
            code_hash="recovery-hash-1",
            used_at=None,
        )
    )
    db_session.add(
        AuthorizationCode(
            code_hash="auth-code-hash-1",
            client_id=client_model.id,
            user_id=user.id,
            redirect_uri="http://localhost:3001/callback",
            scope="openid",
            nonce="n",
            code_challenge="c",
            code_challenge_method="S256",
            expires_at=_now() + timedelta(minutes=10),
        )
    )
    db_session.add(
        ClientUserBlock(
            client_id=client_model.id,
            user_id=user.id,
            email=user.email,
            reason="test",
        )
    )
    db_session.add(
        Otp(
            purpose=OtpPurpose.reset_password,
            target=user.email,
            code_hash="otp-hash-1",
            expires_at=_now() + timedelta(minutes=10),
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/me/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200

    assert db_session.scalar(
        select(SessionModel).where(SessionModel.user_id == user.id)
    ) is None
    assert db_session.scalar(
        select(RecoveryCode).where(RecoveryCode.user_id == user.id)
    ) is None
    assert db_session.scalar(
        select(UserConsent).where(UserConsent.user_id == user.id)
    ) is None
    assert db_session.scalar(
        select(AuthorizationCode).where(AuthorizationCode.user_id == user.id)
    ) is None
    assert db_session.scalar(
        select(ClientUserBlock).where(ClientUserBlock.user_id == user.id)
    ) is None
    assert db_session.scalar(
        select(Otp).where(Otp.target == "a@example.com")
    ) is None


def test_last_admin_cannot_cancel_account(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    user.role = UserRole.admin
    db_session.commit()

    response = client.post(
        "/api/v1/me/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "最后一位管理员不能注销账号"

    db_session.add(
        User(
            email="admin2@example.com",
            password_hash=hash_password("password123"),
            nickname="Admin2",
            role=UserRole.admin,
        )
    )
    db_session.commit()

    response = client.post(
        "/api/v1/me/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert db_session.scalar(
        select(User).where(User.email == "a@example.com")
    ) is None


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


def test_admin_delete_user_requires_admin_password_and_logs_audit(
    client, captured_email, db_session
) -> None:
    admin = _login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)

    response = client.post(
        f"/api/v1/admin/users/{bob.id}/delete",
        json={"current_password": "wrong-password"},
    )
    assert response.status_code == 400
    assert (
        db_session.scalar(select(User).where(User.id == bob.id)) is not None
    )

    response = client.post(
        f"/api/v1/admin/users/{bob.id}/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    assert len(
        [m for m in captured_email.messages if m[0] == "account_deleted"]
    ) == 1
    assert db_session.scalar(select(User).where(User.id == bob.id)) is None
    # 旧会话失效，无法再登录
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "bob@example.com", "password": "password123"},
        ).status_code
        == 401
    )

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_delete_user")
    ).all()
    assert len(logs) == 1
    assert logs[0].actor_id == str(admin.id)
    assert logs[0].target_id == str(bob.id)


def test_admin_delete_restrictions(client, db_session) -> None:
    admin = _login_admin(client, db_session)
    other_admin = User(
        email="admin2@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin2",
        role=UserRole.admin,
    )
    db_session.add(other_admin)
    db_session.commit()
    db_session.refresh(other_admin)

    # 不能删除自己
    response = client.post(
        f"/api/v1/admin/users/{admin.id}/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 400
    assert "不能删除自己" in response.json()["detail"]

    # 不能直接删除其他管理员
    response = client.post(
        f"/api/v1/admin/users/{other_admin.id}/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 403
    assert (
        db_session.scalar(select(User).where(User.id == other_admin.id))
        is not None
    )


def test_non_admin_cannot_delete_users(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    response = client.post(
        f"/api/v1/admin/users/{user.id}/delete",
        json={"current_password": "password123"},
    )
    assert response.status_code == 403
    assert db_session.get(User, user.id) is not None
