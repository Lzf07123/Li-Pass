"""更换邮箱：新邮箱验证码 + 当前密码复核的闭环与边界。"""

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User
from tests.helpers import login_with_email_2fa, register_and_login


def _request(client, captured_email, new_email, password):
    return client.post(
        "/api/v1/me/email/change/request",
        json={"new_email": new_email, "current_password": password},
    )


def test_request_rejects_wrong_password(client, captured_email) -> None:
    register_and_login(client, captured_email)
    before = len(captured_email.messages)
    resp = _request(client, captured_email, "b@example.com", "wrong-password")
    assert resp.status_code == 400
    assert len(captured_email.messages) == before


def test_request_rejects_same_email(client, captured_email) -> None:
    register_and_login(client, captured_email)
    resp = _request(client, captured_email, "a@example.com", "password123")
    assert resp.status_code == 400


def test_request_rejects_taken_email(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    db_session.add(
        User(
            email="taken@example.com",
            password_hash="x",
            nickname="T",
        )
    )
    db_session.commit()
    resp = _request(client, captured_email, "taken@example.com", "password123")
    assert resp.status_code == 409


def test_change_flow_updates_email_audits_and_notifies_old(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    resp = _request(client, captured_email, "new@example.com", "password123")
    assert resp.status_code == 200
    # 验证码发送到新邮箱
    assert captured_email.messages[-1][:2] == ("verification", "new@example.com")
    code = captured_email.messages[-1][2]

    resp = client.post(
        "/api/v1/me/email/change/confirm",
        json={"new_email": "new@example.com", "code": code},
    )
    assert resp.status_code == 200
    user = db_session.scalar(select(User).where(User.email == "new@example.com"))
    assert user is not None
    assert db_session.scalar(select(User).where(User.email == "a@example.com")) is None
    # 旧邮箱收到变更提醒（不含新地址）
    assert ("email_changed", "a@example.com") in [
        (kind, to) for kind, to, *_ in captured_email.messages
    ]
    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "email_change")
    )
    assert audit is not None
    assert audit.detail == {
        "old_email": "a@example.com",
        "new_email": "new@example.com",
    }


def test_confirm_rejects_wrong_code(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    assert _request(client, captured_email, "new@example.com", "password123").status_code == 200
    resp = client.post(
        "/api/v1/me/email/change/confirm",
        json={"new_email": "new@example.com", "code": "000000"},
    )
    assert resp.status_code == 400
    assert db_session.scalar(select(User).where(User.email == "a@example.com")) is not None


def test_request_requires_explicit_password_despite_stepup_window(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    # 打开 step-up 窗口
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )
    resp = _request(client, captured_email, "new@example.com", "")
    # 空密码在参数校验层即被拒绝（422），窗口绝不豁免
    assert resp.status_code == 422


def test_change_keeps_login_and_twofa_on_new_email(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    _request(client, captured_email, "new@example.com", "password123")
    code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/me/email/change/confirm",
            json={"new_email": "new@example.com", "code": code},
        ).status_code
        == 200
    )
    # 登出后旧邮箱登录失败，新邮箱登录 + 2FA 成功
    client.post("/api/v1/auth/logout")
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "password123"},
        ).status_code
        == 401
    )
    resp = login_with_email_2fa(
        client, captured_email, "new@example.com", "password123"
    )
    assert resp.status_code == 200
