import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import generate_token, hash_token
from tests.helpers import register_and_login


def login_admin(client, db_session) -> None:
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


def create_session(db_session, user, token=None, **overrides) -> tuple[SessionModel, str]:
    token = token or generate_token()
    now = datetime.now(timezone.utc)
    values = {
        "user_id": user.id,
        "token_hash": hash_token(token),
        "auth_method": "password",
        "device_name": "Chrome on macOS",
        "ip": "203.0.113.7",
        "user_agent": "Mozilla/5.0 test-agent",
        "expires_at": now + timedelta(days=1),
        "last_used_at": now,
    }
    values.update(overrides)
    session = SessionModel(**values)
    db_session.add(session)
    db_session.commit()
    return session, token


def test_admin_list_sessions_with_search(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    bob_session, _ = create_session(db_session, bob, device_name="Safari on iPhone")

    sessions = client.get("/api/v1/admin/sessions").json()["items"]
    assert len(sessions) >= 2
    bob_item = next(s for s in sessions if s["id"] == str(bob_session.id))
    assert bob_item["user"]["email"] == "bob@example.com"
    assert bob_item["device_name"] == "Safari on iPhone"
    assert bob_item["auth_method"] == "password"
    assert any(s["current"] is True for s in sessions)

    result = client.get("/api/v1/admin/sessions", params={"q": "bob"}).json()[
        "items"
    ]
    assert [s["id"] for s in result] == [str(bob_session.id)]

    result = client.get(
        "/api/v1/admin/sessions", params={"q": "203.0.113"}
    ).json()["items"]
    assert any(s["id"] == str(bob_session.id) for s in result)


def test_admin_sessions_include_ip_location(client, db_session, monkeypatch) -> None:
    from app.api.routes import admin_sessions as routes

    monkeypatch.setattr(
        routes, "describe_ip", lambda ip: "广东省 深圳市", raising=False
    )
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    bob_session, _ = create_session(db_session, bob, ip="203.0.113.7")

    items = client.get("/api/v1/admin/sessions").json()["items"]
    bob_item = next(item for item in items if item["id"] == str(bob_session.id))
    assert bob_item["ip_location"] == "广东省 深圳市"


def test_admin_list_excludes_expired_sessions(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    now = datetime.now(timezone.utc)
    expired, _ = create_session(
        db_session, bob, expires_at=now - timedelta(days=1)
    )

    sessions = client.get("/api/v1/admin/sessions").json()["items"]
    assert all(s["id"] != str(expired.id) for s in sessions)
    db_session.refresh(expired)
    assert expired.revoked_at is not None


def test_admin_list_sessions_paginates_in_sql(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    for index in range(5):
        create_session(db_session, bob, device_name=f"Device {index}")

    page1 = client.get(
        "/api/v1/admin/sessions", params={"limit": 2}
    ).json()
    page2 = client.get(
        "/api/v1/admin/sessions", params={"limit": 2, "offset": 2}
    ).json()

    # bob 的 5 个会话 + 管理员自己的 1 个会话
    assert page1["total"] == 6
    assert len(page1["items"]) == 2
    assert len(page2["items"]) == 2
    first_ids = {s["id"] for s in page1["items"]}
    second_ids = {s["id"] for s in page2["items"]}
    assert first_ids.isdisjoint(second_ids)


def test_admin_revoke_session(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    token = generate_token()
    session, _ = create_session(db_session, bob, token=token)

    response = client.delete(f"/api/v1/admin/sessions/{session.id}")
    assert response.status_code == 204
    db_session.refresh(session)
    assert session.revoked_at is not None

    audit = db_session.scalar(
        select(AuditLog).where(AuditLog.action == "admin_revoke_session")
    )
    assert audit is not None
    assert audit.actor_type == "admin"
    assert audit.target_id == str(session.id)
    assert audit.detail["email"] == "bob@example.com"

    # 被踢出的会话令牌应立即失效，不能再访问任何接口。
    settings = get_settings()
    client.cookies.set(settings.session_cookie_name, token)
    assert client.get("/api/v1/me").status_code == 401


def test_admin_cannot_revoke_current_session(client, db_session) -> None:
    login_admin(client, db_session)
    sessions = client.get("/api/v1/admin/sessions").json()["items"]
    current = next(s for s in sessions if s["current"] is True)
    response = client.delete(f"/api/v1/admin/sessions/{current['id']}")
    assert response.status_code == 400
    assert response.json()["detail"] == "不能下线当前会话"


def test_admin_revoke_missing_session_returns_404(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.delete(f"/api/v1/admin/sessions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_admin_batch_revoke_sessions(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    first, _ = create_session(db_session, bob, device_name="Device 1")
    second, _ = create_session(db_session, bob, device_name="Device 2")

    response = client.post(
        "/api/v1/admin/sessions/batch-revoke",
        json={"session_ids": [str(first.id), str(second.id)]},
    )
    assert response.status_code == 200
    assert response.json() == {"revoked": 2, "skipped": 0}
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.revoked_at is not None
    assert second.revoked_at is not None

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "admin_batch_revoke_session"
        )
    )
    assert audit is not None
    assert audit.actor_type == "admin"
    assert audit.detail["count"] == 2
    assert sorted(audit.detail["emails"]) == [
        "bob@example.com",
        "bob@example.com",
    ]


def test_admin_batch_revoke_skips_current_missing_and_revoked(
    client, db_session
) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    active, _ = create_session(db_session, bob, device_name="Active")
    revoked, _ = create_session(db_session, bob, device_name="Revoked")
    revoked.revoked_at = datetime.now(timezone.utc)
    db_session.commit()

    sessions = client.get("/api/v1/admin/sessions").json()["items"]
    current_id = next(s["id"] for s in sessions if s["current"])

    response = client.post(
        "/api/v1/admin/sessions/batch-revoke",
        json={
            "session_ids": [
                str(active.id),
                str(revoked.id),
                current_id,
                str(uuid.uuid4()),
            ]
        },
    )
    assert response.status_code == 200
    assert response.json() == {"revoked": 1, "skipped": 3}
    db_session.refresh(active)
    assert active.revoked_at is not None
    current = db_session.get(SessionModel, uuid.UUID(current_id))
    assert current.revoked_at is None


def test_admin_batch_revoke_requires_non_empty_ids(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.post(
        "/api/v1/admin/sessions/batch-revoke", json={"session_ids": []}
    )
    assert response.status_code == 422


def test_admin_batch_revoke_rate_limited(client, db_session) -> None:
    login_admin(client, db_session)
    from app.services.rate_limit import get_rate_limiter

    admin = db_session.scalar(
        select(User).where(User.email == "admin@example.com")
    )
    get_rate_limiter().hit(
        "admin_session_revoke", str(admin.id), 60, increment=31
    )
    response = client.post(
        "/api/v1/admin/sessions/batch-revoke",
        json={"session_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 429


def test_admin_revoke_all_sessions_except_current(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    first, _ = create_session(db_session, bob, device_name="Device 1")
    second, _ = create_session(db_session, bob, device_name="Device 2")

    response = client.post("/api/v1/admin/sessions/revoke-all")
    assert response.status_code == 200
    assert response.json() == {"revoked": 2}
    db_session.refresh(first)
    db_session.refresh(second)
    assert first.revoked_at is not None
    assert second.revoked_at is not None

    remaining = client.get("/api/v1/admin/sessions").json()["items"]
    assert len(remaining) == 1
    assert remaining[0]["current"] is True

    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.action == "admin_revoke_all_sessions"
        )
    )
    assert audit is not None
    assert audit.detail["count"] == 2


def test_admin_revoke_all_rate_limited(client, db_session) -> None:
    login_admin(client, db_session)
    from app.services.rate_limit import get_rate_limiter

    admin = db_session.scalar(
        select(User).where(User.email == "admin@example.com")
    )
    get_rate_limiter().hit(
        "admin_session_revoke", str(admin.id), 60, increment=31
    )
    response = client.post("/api/v1/admin/sessions/revoke-all")
    assert response.status_code == 429


def test_admin_revoke_all_keeps_current_when_only_session(
    client, db_session
) -> None:
    login_admin(client, db_session)
    response = client.post("/api/v1/admin/sessions/revoke-all")
    assert response.status_code == 200
    assert response.json() == {"revoked": 0}
    remaining = client.get("/api/v1/admin/sessions").json()["items"]
    assert len(remaining) == 1
    assert remaining[0]["current"] is True


def test_non_admin_cannot_access_session_monitoring(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    assert client.get("/api/v1/admin/sessions").status_code == 403
    assert (
        client.delete(f"/api/v1/admin/sessions/{uuid.uuid4()}").status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/admin/sessions/batch-revoke",
            json={"session_ids": [str(uuid.uuid4())]},
        ).status_code
        == 403
    )
    assert (
        client.post("/api/v1/admin/sessions/revoke-all").status_code == 403
    )
