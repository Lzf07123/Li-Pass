from datetime import datetime, timedelta, timezone

from app.models.account_invite import AccountInvite
from app.models.user import User
from app.security.tokens import hash_token


def _invite(db_session, token: str = "tok-1", **overrides) -> AccountInvite:
    values = {
        "email": "invitee@example.com",
        "token_hash": hash_token(token),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }
    values.update(overrides)
    invite = AccountInvite(**values)
    db_session.add(invite)
    db_session.commit()
    return invite


def test_invite_status_valid(client, db_session) -> None:
    _invite(db_session)
    resp = client.get("/api/v1/auth/invite/status", params={"token": "tok-1"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["email"] == "i***@example.com"
    assert body["email_taken"] is False


def test_invite_status_unknown_token(client) -> None:
    resp = client.get("/api/v1/auth/invite/status", params={"token": "nope"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "邀请链接无效"


def test_invite_status_used(client, db_session) -> None:
    _invite(db_session, used_at=datetime.now(timezone.utc))
    resp = client.get("/api/v1/auth/invite/status", params={"token": "tok-1"})
    assert resp.status_code == 410
    assert "已被使用" in resp.json()["detail"]


def test_invite_status_cancelled(client, db_session) -> None:
    _invite(db_session, cancelled_at=datetime.now(timezone.utc))
    resp = client.get("/api/v1/auth/invite/status", params={"token": "tok-1"})
    assert resp.status_code == 410
    assert "已被取消" in resp.json()["detail"]


def test_invite_status_expired(client, db_session) -> None:
    _invite(
        db_session,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    resp = client.get("/api/v1/auth/invite/status", params={"token": "tok-1"})
    assert resp.status_code == 410
    assert "已过期" in resp.json()["detail"]


def test_invite_status_email_taken(client, db_session) -> None:
    _invite(db_session)
    db_session.add(
        User(
            email="invitee@example.com",
            password_hash="x",
            nickname="U",
        )
    )
    db_session.commit()
    resp = client.get("/api/v1/auth/invite/status", params={"token": "tok-1"})
    assert resp.status_code == 200
    assert resp.json()["email_taken"] is True
