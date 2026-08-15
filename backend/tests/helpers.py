import base64
import hashlib

from app.models.oauth_client import OAuthClient
from app.services.rate_limit import get_rate_limiter

TEST_VERIFIER = "v" * 43


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def register_and_login(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})
    login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )


def login_with_email_2fa(
    client,
    captured_email,
    email: str,
    password: str,
    headers: dict | None = None,
    **login_kwargs,
):
    """登录并透明地完成邮箱 2FA 挑战（无 2FA 时直接建立会话）。

    强制 2FA 落地后，已验证邮箱的账号登录会返回 requires_2fa；
    此辅助函数按需发送验证码并完成挑战，保证测试拿到已登录会话。
    """
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password, **login_kwargs},
        headers=headers,
    )
    if response.status_code != 200 or not response.json().get("requires_2fa"):
        return response
    challenge_id = response.json()["challenge_id"]
    # 同一测试内多次登录会触发 60 秒重发冷却与每小时配额，
    # 测试侧先清理内存限流计数（生产行为的冷却由 test_twofa_login 单独覆盖）。
    get_rate_limiter().reset("otp_resend_cooldown", email)
    get_rate_limiter().reset("otp_send", email)
    client.post(
        "/api/v1/auth/2fa/send",
        json={"challenge_id": challenge_id},
        headers=headers,
    )
    code = captured_email.messages[-1][2]
    return client.post(
        "/api/v1/auth/2fa/verify",
        json={
            "challenge_id": challenge_id,
            "method": "email_otp",
            "code": code,
        },
        headers=headers,
    )


def critical_stepup_payload(
    client,
    captured_email,
    email: str,
    password: str = "password123",
    method: str = "email_otp",
    code: str | None = None,
) -> dict:
    """构造注销/删除账号所需的「密码 + 任意 2FA」载荷。

    默认用邮箱验证码：先调用 /me/step-up/send（作用于当前会话用户），
    再从 captured_email 取最新验证码；测试侧清理发送冷却与配额。
    """
    get_rate_limiter().reset("otp_resend_cooldown", email)
    get_rate_limiter().reset("otp_send", email)
    if method == "email_otp" and code is None:
        client.post("/api/v1/me/step-up/send")
        code = captured_email.messages[-1][2]
    return {
        "current_password": password,
        "stepup_method": method,
        "stepup_code": code or "",
    }


def create_client(db_session, **overrides) -> OAuthClient:
    values = {
        "client_id": "cli_demo",
        "name": "Demo",
        "redirect_uris": ["http://localhost:3001/callback"],
        "scopes": ["openid", "profile", "email"],
    }
    values.update(overrides)
    client = OAuthClient(**values)
    db_session.add(client)
    db_session.commit()
    return client


def authorize_params(overrides=None) -> dict:
    params = {
        "response_type": "code",
        "client_id": "cli_demo",
        "redirect_uri": "http://localhost:3001/callback",
        "scope": "openid profile",
        "state": "st-1",
        "nonce": "n-1",
        "code_challenge": challenge_for(TEST_VERIFIER),
        "code_challenge_method": "S256",
    }
    if overrides:
        params.update(overrides)
    return params
