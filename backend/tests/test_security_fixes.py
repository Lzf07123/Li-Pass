import hashlib
from pathlib import Path

import pyotp
from sqlalchemy import select

from app.core.config import get_settings
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from tests.helpers import login_with_email_2fa, register_and_login


def test_avatar_url_rejects_path_traversal(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.put(
        "/api/v1/me",
        json={"avatar_url": "/uploads/avatars/../../.env"},
    )
    assert response.status_code == 422

    response = client.put(
        "/api/v1/me",
        json={"avatar_url": "http://a.png"},
    )
    assert response.status_code == 200


def test_csrf_foreign_origin_rejected(client, captured_email) -> None:
    register_and_login(client, captured_email)
    response = client.post(
        "/api/v1/me/password",
        json={"current_password": "password123", "new_password": "newpassword456"},
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403


def test_password_reset_revokes_sessions(client, captured_email) -> None:
    client.post(
        "/api/v1/auth/register",
        json={"email": "a@example.com", "password": "password123", "nickname": "Alice"},
    )
    code = captured_email.messages[-1][2]
    client.post("/api/v1/auth/email/verify", json={"email": "a@example.com", "code": code})
    assert client.get("/api/v1/me").status_code == 401
    login_with_email_2fa(
        client, captured_email, "a@example.com", "password123"
    )
    assert client.get("/api/v1/me").status_code == 200

    client.post("/api/v1/auth/password/reset", json={"email": "a@example.com"})
    reset_code = captured_email.messages[-1][2]
    assert (
        client.post(
            "/api/v1/auth/password/reset/confirm",
            json={
                "email": "a@example.com",
                "code": reset_code,
                "new_password": "newpassword456",
            },
        ).status_code
        == 200
    )
    # 旧会话必须失效。
    assert client.get("/api/v1/me").status_code == 401


def test_recovery_codes_use_hmac_and_high_entropy(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    setup = client.get("/api/v1/me/2fa/totp/setup").json()
    secret = setup["secret"]

    enable = client.post(
        "/api/v1/me/2fa/totp/enable",
        json={
            "code": pyotp.TOTP(secret).now(),
            "secret": secret,
            "current_password": "password123",
        },
    ).json()
    code = enable["recovery_codes"][0]
    assert len(code) == 32
    stored = db_session.scalar(select(RecoveryCode)).code_hash
    assert stored != hashlib.sha256(code.encode()).hexdigest()


def test_avatar_delete_scoped_to_own_directory(client, captured_email) -> None:
    register_and_login(client, captured_email)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    own = client.post(
        "/api/v1/me/avatar",
        files={"file": ("a.png", png, "image/png")},
    ).json()["avatar_url"]
    upload_dir = Path(get_settings().avatar_upload_dir)
    old_path = upload_dir / own.removeprefix("/uploads/avatars/")
    # 直接上传新头像：自己的旧头像应被正常替换删除。
    client.post(
        "/api/v1/me/avatar",
        files={"file": ("b.png", png, "image/png")},
    )
    assert not old_path.exists()

    # 另一个用户的头像文件，构造在其用户目录下。
    victim_rel = (
        "00000000-0000-0000-0000-000000000001/"
        "deadbeefdeadbeefdeadbeefdeadbeef.jpg"
    )
    victim_path = upload_dir / victim_rel
    victim_path.parent.mkdir(parents=True, exist_ok=True)
    victim_path.write_bytes(png)

    # 把自己的 avatar_url 指向受害者的头像，再上传新头像：不得删除受害者文件。
    client.put("/api/v1/me", json={"avatar_url": f"/uploads/avatars/{victim_rel}"})
    response = client.post(
        "/api/v1/me/avatar",
        files={"file": ("c.png", png, "image/png")},
    )
    assert response.status_code == 200
    assert victim_path.exists(), "跨用户头像文件不应被删除"
