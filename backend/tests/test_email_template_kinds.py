"""验证码邮件按「将要进行的操作」区分模板类型。

每个发信接口都必须显式传入正确的 VerificationKind，邮件正文因此能写明
该验证码将用于哪种操作（注册/登录/敏感操作复核/更换邮箱/绑定手机号），
防止验证码被误用到其它操作或被钓鱼转发。
"""

from app.services.rate_limit import get_rate_limiter
from tests.helpers import login_with_email_2fa, register_and_login


def _reset_send_quotas(email: str) -> None:
    get_rate_limiter().reset("otp_resend_cooldown", email)
    get_rate_limiter().reset("otp_send", email)
    get_rate_limiter().reset("email_change_cooldown", email)
    get_rate_limiter().reset("email_change_send", email)


def test_register_email_uses_register_kind(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "Alice",
        },
    )
    message = captured_email.messages[-1]
    assert message[0] == "verification"
    assert message[1] == "a@example.com"
    assert len(message[2]) == 6
    assert message[3] == "register"


def test_login_twofa_email_uses_login_kind(client, captured_email) -> None:
    register_and_login(client, captured_email)
    assert captured_email.messages[-1][3] == "login_2fa"


def test_stepup_email_uses_step_up_kind(client, captured_email) -> None:
    register_and_login(client, captured_email)
    _reset_send_quotas("a@example.com")
    response = client.post("/api/v1/me/step-up/send")
    assert response.status_code == 200
    assert captured_email.messages[-1][3] == "step_up"


def test_change_email_verification_uses_change_email_kind(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    _reset_send_quotas("a@example.com")
    response = client.post(
        "/api/v1/me/email/change/request",
        json={"new_email": "new@example.com", "current_password": "password123"},
    )
    assert response.status_code == 200
    message = captured_email.messages[-1]
    assert message[0] == "verification"
    assert message[1] == "new@example.com"
    assert len(message[2]) == 6
    assert message[3] == "change_email"


def test_bind_phone_verification_uses_bind_phone_kind(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)
    _reset_send_quotas("a@example.com")
    response = client.post("/api/v1/me/phone/bind/send")
    assert response.status_code == 200
    assert captured_email.messages[-1][3] == "bind_phone"


def test_password_reset_email_uses_reset_kind(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": "password123",
            "nickname": "Alice",
        },
    )
    before = len(captured_email.messages)
    response = client.post(
        "/api/v1/auth/password/reset", json={"email": "a@example.com"}
    )
    assert response.status_code == 202
    assert captured_email.messages[-1][0] == "reset"
    assert captured_email.messages[-1][1] == "a@example.com"
    assert len(captured_email.messages) == before + 1
