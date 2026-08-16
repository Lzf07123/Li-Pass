from sqlalchemy import select

import app.api.routes.auth as auth_module
from app.models.user import User


def test_register_verify_updates_user(client, db_session, captured_email) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "A@Example.com", "password": "password123", "nickname": "Alice"},
    )
    assert response.status_code == 201
    assert "message" in response.json()

    code = captured_email.messages[0][2]
    response = client.post(
        "/api/v1/auth/email/verify",
        json={"email": "a@example.com", "code": code},
    )
    assert response.status_code == 200

    user = db_session.scalar(select(User).where(User.email == "a@example.com"))
    assert user is not None
    assert user.email_verified_at is not None
    # 强制 2FA：验证邮箱后直接启用邮箱验证码作为默认方案。
    assert user.email_otp_enabled is True


def test_register_duplicate_email(client, captured_email) -> None:
    payload = {"email": "a@example.com", "password": "password123", "nickname": "Alice"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    # 防枚举：重复注册也返回 201，且不重复发信。
    response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert len(captured_email.messages) == 1


def test_resend_verification_email(client, captured_email, db_session) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "resend@example.com", "password": "password123", "nickname": "R"},
    )
    assert response.status_code == 201
    assert len(captured_email.messages) == 1

    resend = client.post(
        "/api/v1/auth/email/verify/resend",
        json={"email": "resend@example.com"},
    )
    assert resend.status_code == 200
    assert (
        resend.json()["message"]
        == "请求已受理：如果该邮箱尚未验证，验证邮件将发送至该邮箱。"
    )
    assert len(captured_email.messages) == 2

    code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/auth/email/verify",
            json={"email": "resend@example.com", "code": code},
        ).status_code
        == 200
    )

    before = len(captured_email.messages)
    # 已验证邮箱不再触发重发，返回相同文案。
    assert (
        client.post(
            "/api/v1/auth/email/verify/resend",
            json={"email": "resend@example.com"},
        ).status_code
        == 200
    )
    assert len(captured_email.messages) == before


def test_me_requires_session(client) -> None:
    assert client.get("/api/v1/me").status_code == 401


def test_register_status_reports_switch(client, monkeypatch) -> None:
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }
    monkeypatch.setattr(
        auth_module.settings, "public_registration_enabled", False
    )
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": False
    }


def test_register_rejected_when_public_registration_closed(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        auth_module.settings, "public_registration_enabled", False
    )
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    assert response.status_code == 403


def test_register_cross_site_origin_rejected(client) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
        headers={"Origin": "http://evil.example"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "跨站请求被拒绝"


def test_invite_register_unaffected_by_public_switch(client, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_module.settings, "public_registration_enabled", False
    )
    # 邀请注册不受公开注册开关影响
    assert (
        client.post(
            "/api/v1/auth/invite/register",
            json={"token": "x" * 43, "nickname": "Invitee", "password": "password123"},
        ).status_code
        == 400
    )


def test_resend_failure_preserves_old_code(
    client, captured_email, monkeypatch
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    old_code = captured_email.messages[-1][2]

    class FlakyEmail:
        def __init__(self, base):
            self.base = base
            self.fail_next = True

        def send_verification(self, to, code):
            if self.fail_next:
                self.fail_next = False
                raise RuntimeError("smtp down")
            self.base.send_verification(to, code)

    monkeypatch.setattr(
        "app.api.routes.auth.get_email_service",
        lambda: FlakyEmail(captured_email),
    )
    response = client.post(
        "/api/v1/auth/email/verify/resend",
        json={"email": "a@example.com"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "邮件发送失败，请稍后重试"

    # 发送失败时回滚新验证码，旧验证码仍然有效
    assert (
        client.post(
            "/api/v1/auth/email/verify",
            json={"email": "a@example.com", "code": old_code},
        ).status_code
        == 200
    )


def test_verify_locked_after_too_many_wrong_codes(
    client, captured_email
) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    for _ in range(5):
        assert (
            client.post(
                "/api/v1/auth/email/verify",
                json={"email": "a@example.com", "code": "000000"},
            ).status_code
            == 400
        )
    response = client.post(
        "/api/v1/auth/email/verify",
        json={"email": "a@example.com", "code": "000000"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "验证码错误次数过多，请重新发送验证码"

    # 重新发送后获得新验证码，可继续验证
    client.post(
        "/api/v1/auth/email/verify/resend",
        json={"email": "a@example.com"},
    )
    new_code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/auth/email/verify",
            json={"email": "a@example.com", "code": new_code},
        ).status_code
        == 200
    )


def test_resend_verify_rate_limit_keyed_by_email_not_ip(
    client, captured_email, monkeypatch
) -> None:
    from app.services.rate_limit import MemoryRateLimiter

    limiter = MemoryRateLimiter()
    original_hit = limiter.hit
    keys: list[tuple[str, str]] = []

    def hit(scope, key, window_seconds, increment=1):
        keys.append((scope, key))
        return original_hit(scope, key, window_seconds, increment)

    monkeypatch.setattr(limiter, "hit", hit)
    monkeypatch.setattr("app.api.routes.auth.get_rate_limiter", lambda: limiter)
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    assert (
        client.post(
            "/api/v1/auth/email/verify/resend",
            json={"email": "a@example.com"},
        ).status_code
        == 200
    )
    resend_keys = [key for scope, key in keys if scope == "email_resend"]
    assert resend_keys == ["a@example.com"]
    assert all(":" not in key for key in resend_keys)


def test_verify_attempts_rate_limit_keyed_by_email_not_ip(
    client, captured_email, monkeypatch
) -> None:
    from app.services.rate_limit import MemoryRateLimiter

    limiter = MemoryRateLimiter()
    original_hit = limiter.hit
    keys: list[tuple[str, str]] = []

    def hit(scope, key, window_seconds, increment=1):
        keys.append((scope, key))
        return original_hit(scope, key, window_seconds, increment)

    monkeypatch.setattr(limiter, "hit", hit)
    monkeypatch.setattr("app.api.routes.auth.get_rate_limiter", lambda: limiter)
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    assert (
        client.post(
            "/api/v1/auth/email/verify",
            json={"email": "a@example.com", "code": "000000"},
        ).status_code
        == 400
    )
    verify_keys = [key for scope, key in keys if scope == "email_verify"]
    assert verify_keys == ["a@example.com"]
    assert all(":" not in key for key in verify_keys)
