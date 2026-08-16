"""审计修复回归测试（2026-08-16 安全审查发现清单）。

每个用例对应审计报告中的一个修复点；先在旧实现上红（预期失败），
再以最小改动转绿，防止回归。
"""

import shutil
import urllib.parse
import base64

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_db
from app.main import create_app
from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_token
from app.services.oidc import create_authorization_code
from tests.helpers import (
    authorize_params,
    challenge_for,
    create_client,
    login_with_email_2fa,
    register_and_login,
)


def _register_and_login_second_user(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "b@example.com",
            "password": "password123",
            "nickname": "Bob",
        },
    )
    code = captured_email.messages[-1][2]
    client.post(
        "/api/v1/auth/email/verify",
        json={"email": "b@example.com", "code": code},
    )
    login_with_email_2fa(
        client, captured_email, "b@example.com", "password123"
    )


def _logout_request_id(client, db_session) -> str:
    create_client(
        db_session,
        client_id="cli_logout",
        redirect_uris=["http://x/cb"],
        post_logout_redirect_uris=["https://x/after-logout"],
    )
    started = client.get(
        "/oauth2/end-session",
        params={
            "client_id": "cli_logout",
            "post_logout_redirect_uri": "https://x/after-logout",
            "state": "st-9",
        },
    )
    query = urllib.parse.urlsplit(started.headers["location"]).query
    return dict(urllib.parse.parse_qsl(query))["request_id"]


def test_confirm_logout_request_rejects_foreign_session(
    client, db_session, captured_email
) -> None:
    """A 发起的登出确认请求，B 的会话不得确认，也不能因此被踢下线。"""
    register_and_login(client, captured_email)
    request_id = _logout_request_id(client, db_session)
    _register_and_login_second_user(client, captured_email)

    resp = client.post(
        f"/api/v1/oauth/logout-requests/{request_id}/confirm"
    )
    assert resp.status_code == 404
    assert client.get("/api/v1/me").status_code == 200


def test_local_only_logout_requires_session(
    client, db_session, captured_email
) -> None:
    """仅登出本网站必须由登录会话执行：无会话返回 401。"""
    register_and_login(client, captured_email)
    request_id = _logout_request_id(client, db_session)

    client.cookies.clear()
    resp = client.post(
        f"/api/v1/oauth/logout-requests/{request_id}/local-only"
    )
    assert resp.status_code == 401


def test_local_only_logout_rejects_foreign_session(
    client, db_session, captured_email
) -> None:
    """仅登出本网站必须匹配发起会话：他人会话返回 404。"""
    register_and_login(client, captured_email)
    request_id = _logout_request_id(client, db_session)
    _register_and_login_second_user(client, captured_email)

    resp = client.post(
        f"/api/v1/oauth/logout-requests/{request_id}/local-only"
    )
    assert resp.status_code == 404


def test_bind_phone_duplicate_returns_409(client, captured_email) -> None:
    """同一手机号被第二个账号绑定时返回 409，而不是 500。"""
    register_and_login(client, captured_email)
    client.post("/api/v1/me/phone/bind/send")
    code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/me/phone/bind",
            json={"phone": "+8613800000001", "code": code},
        ).status_code
        == 200
    )

    _register_and_login_second_user(client, captured_email)
    client.post("/api/v1/me/phone/bind/send")
    code = captured_email.messages[-1][2]
    resp = client.post(
        "/api/v1/me/phone/bind",
        json={"phone": "+8613800000001", "code": code},
    )
    assert resp.status_code == 409


def test_client_block_rejects_malformed_user_id(client, db_session) -> None:
    """畸形 user_id 应在参数校验层返回 422，而不是语义错位的 409。"""
    db_session.add(
        OAuthClient(
            client_id="cli_bad",
            client_secret_hash=hash_token("secret123"),
            name="Bad",
            redirect_uris=["http://x/cb"],
        )
    )
    db_session.commit()
    token = base64.b64encode(b"cli_bad:secret123").decode()
    resp = client.post(
        "/oauth2/client/blocks",
        headers={"Authorization": f"Basic {token}"},
        json={"user_id": "not-a-uuid", "reason": "x"},
    )
    assert resp.status_code == 422


def _login_admin(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            nickname="Admin",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )


def test_create_client_rejects_unsupported_scope(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "PhoneScope",
            "redirect_uris": ["http://localhost:9002/cb"],
            "scopes": ["openid", "phone"],
        },
    )
    assert resp.status_code == 422


def test_create_client_requires_openid_scope(client, db_session) -> None:
    _login_admin(client, db_session)
    resp = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "NoOpenid",
            "redirect_uris": ["http://localhost:9002/cb"],
            "scopes": ["profile"],
        },
    )
    assert resp.status_code == 422


def test_update_client_rejects_empty_redirect_uris(client, db_session) -> None:
    _login_admin(client, db_session)
    oauth_client = create_client(
        db_session, client_id="cli_empty", name="Empty"
    )
    resp = client.patch(
        f"/api/v1/admin/clients/{oauth_client.id}",
        json={"redirect_uris": []},
    )
    assert resp.status_code == 422


def test_update_client_rejects_empty_scopes(client, db_session) -> None:
    _login_admin(client, db_session)
    oauth_client = create_client(
        db_session, client_id="cli_scopes", name="Scopes"
    )
    resp = client.patch(
        f"/api/v1/admin/clients/{oauth_client.id}",
        json={"scopes": []},
    )
    assert resp.status_code == 422


def test_token_rejects_oversized_code_verifier(client) -> None:
    """超长 code_verifier 在参数校验层被 422 拒绝，避免整体哈希放大。"""
    resp = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": "no-such-code",
            "redirect_uri": "http://x/cb",
            "client_id": "cli_demo",
            "code_verifier": "v" * 1000,
        },
    )
    assert resp.status_code == 422


def test_token_rejects_short_code_verifier(client, db_session) -> None:
    """code_verifier 必须满足 RFC 7636 的 43–128 长度窗口。"""
    user = User(
        email="u@example.com",
        password_hash=hash_password("password123"),
        nickname="U",
    )
    db_session.add(user)
    db_session.commit()
    oauth_client = create_client(db_session, client_id="cli_len")
    short_verifier = "v" * 42
    code = create_authorization_code(
        db_session,
        user,
        oauth_client,
        "http://localhost:3001/callback",
        "openid",
        code_challenge=challenge_for(short_verifier),
    )
    resp = client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "http://localhost:3001/callback",
            "client_id": "cli_len",
            "code_verifier": short_verifier,
        },
    )
    assert resp.status_code == 400
    assert resp.json()["error"] == "invalid_grant"


def test_authorize_rejects_malformed_code_challenge(
    client, db_session, captured_email
) -> None:
    """非 43+ 字符 base64url 的 code_challenge 按 invalid_request 回跳。"""
    register_and_login(client, captured_email)
    create_client(db_session, client_id="cli_demo")
    resp = client.get(
        "/oauth2/authorize",
        params=authorize_params({"code_challenge": "abc"}),
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert location.startswith("http://localhost:3001/callback")
    assert "error=invalid_request" in location


def test_missing_avatar_returns_404_on_fresh_upload_dir(engine) -> None:
    """全新部署头像目录尚不存在时，静态挂载应 404 而非 500。"""
    shutil.rmtree(get_settings().avatar_upload_dir, ignore_errors=True)
    app = create_app()
    factory = sessionmaker(
        bind=engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=False) as test_client:
        resp = test_client.get(
            "/uploads/avatars/00000000-0000-0000-0000-000000000001/nope.png"
        )
    assert resp.status_code == 404
