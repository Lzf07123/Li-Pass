from datetime import datetime, timedelta, timezone

from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole, UserStatus
from app.security.passwords import hash_password
from sqlalchemy import select

TZ = timezone(timedelta(hours=8))


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


def test_stats_access_is_audited(client, db_session) -> None:
    login_admin(client, db_session)
    response = client.get("/api/v1/admin/stats?days=7")
    assert response.status_code == 200

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_view_stats")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["days"] == 7


def test_stats_snapshot_cached_within_ttl(monkeypatch) -> None:
    from app.services import admin_stats

    monkeypatch.setattr(admin_stats, "_CACHE", {})
    calls = []

    def fake_collect(db, days):
        calls.append(days)
        return {"generated_at": "x", "n": len(calls)}

    monkeypatch.setattr(admin_stats, "_collect_stats", fake_collect)

    first = admin_stats.collect_admin_stats(None, 30)
    second = admin_stats.collect_admin_stats(None, 30)
    assert first is second
    assert calls == [30]


def test_stats_cache_keyed_by_days(monkeypatch) -> None:
    from app.services import admin_stats

    monkeypatch.setattr(admin_stats, "_CACHE", {})
    calls = []

    def fake_collect(db, days):
        calls.append(days)
        return {"generated_at": "x"}

    monkeypatch.setattr(admin_stats, "_collect_stats", fake_collect)
    admin_stats.collect_admin_stats(None, 30)
    admin_stats.collect_admin_stats(None, 7)
    assert calls == [30, 7]


def test_stats_cache_expires_after_ttl(monkeypatch) -> None:
    from app.services import admin_stats

    monkeypatch.setattr(admin_stats, "_CACHE", {})
    monkeypatch.setattr(admin_stats, "_CACHE_TTL_SECONDS", 0)
    calls = []

    def fake_collect(db, days):
        calls.append(days)
        return {"generated_at": "x"}

    monkeypatch.setattr(admin_stats, "_collect_stats", fake_collect)
    admin_stats.collect_admin_stats(None, 30)
    admin_stats.collect_admin_stats(None, 30)
    assert calls == [30, 30]


def make_user(db_session, email, **overrides) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=email.split("@")[0],
        **overrides,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def add_login(db_session, user, action="login", created_at=None) -> None:
    db_session.add(
        AuditLog(
            actor_type="user",
            actor_id=str(user.id),
            action=action,
            category="auth",
            created_at=created_at,
        )
    )


def test_admin_stats_requires_auth(client) -> None:
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 401


def test_admin_stats_rejects_non_admin(client, db_session) -> None:
    make_user(db_session, "user@example.com")
    client.post(
        "/api/v1/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    response = client.get("/api/v1/admin/stats")
    assert response.status_code == 403


def test_admin_stats_validates_days_range(client, db_session) -> None:
    login_admin(client, db_session)
    assert client.get("/api/v1/admin/stats?days=6").status_code == 422
    assert client.get("/api/v1/admin/stats?days=91").status_code == 422


def test_admin_stats_overview_counts(client, db_session) -> None:
    now = datetime.now(timezone.utc)
    # 造 3 名种子用户：active/user/verified、admin/verified、disabled/未验证。
    u1 = make_user(
        db_session,
        "u1@example.com",
        status=UserStatus.active,
        email_verified_at=now,
    )
    u2 = make_user(
        db_session,
        "u2@example.com",
        role=UserRole.admin,
        email_verified_at=now,
    )
    make_user(db_session, "u3@example.com", status=UserStatus.disabled)

    # u1 一个已吊销会话，u2 一个在线会话。
    db_session.add_all(
        [
            SessionModel(
                user_id=u1.id,
                token_hash="stats-revoked",
                auth_method="password",
                expires_at=now + timedelta(days=1),
                revoked_at=now,
            ),
            SessionModel(
                user_id=u2.id,
                token_hash="stats-online",
                auth_method="totp",
                expires_at=now + timedelta(days=1),
            ),
        ]
    )
    db_session.commit()

    login_admin(client, db_session)

    response = client.get("/api/v1/admin/stats?days=30")
    assert response.status_code == 200
    overview = response.json()["overview"]
    # 3 名种子用户 + 1 名登录管理员。
    assert overview["total_users"] == 4
    assert overview["active_users"] == 3
    assert overview["disabled_users"] == 1
    assert overview["admins"] == 2
    assert overview["verified_users"] == 2
    # 在线会话：u2 的 totp 会话 + 管理员登录产生的会话。
    assert overview["online_sessions"] == 2
    assert overview["total_logins"] == 1


def test_admin_stats_daily_series_and_auth_methods(client, db_session) -> None:
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    u1 = make_user(db_session, "u1@example.com", created_at=yesterday)
    u2 = make_user(db_session, "u2@example.com", created_at=two_days_ago)
    # 同一用户昨天登录两次 → 次数 2、去重人数 1；另一用户前天 2FA 登录 1 次。
    add_login(db_session, u1, created_at=yesterday)
    add_login(db_session, u1, created_at=yesterday)
    add_login(db_session, u2, action="2fa_login", created_at=two_days_ago)
    db_session.commit()

    # 在线会话认证方式：password×1、totp×1、未知 sso×1；已吊销不统计。
    db_session.add_all(
        [
            SessionModel(
                user_id=u1.id,
                token_hash="stats-password",
                auth_method="password",
                expires_at=now + timedelta(days=1),
            ),
            SessionModel(
                user_id=u2.id,
                token_hash="stats-totp",
                auth_method="totp",
                expires_at=now + timedelta(days=1),
            ),
            SessionModel(
                user_id=u2.id,
                token_hash="stats-sso",
                auth_method="sso",
                expires_at=now + timedelta(days=1),
            ),
            SessionModel(
                user_id=u1.id,
                token_hash="stats-revoked",
                auth_method="password",
                expires_at=now - timedelta(days=1),
                revoked_at=now,
            ),
        ]
    )
    db_session.commit()

    login_admin(client, db_session)
    response = client.get("/api/v1/admin/stats?days=7")
    assert response.status_code == 200
    body = response.json()

    assert body["days"] == 7
    assert body["timezone"] == "Asia/Shanghai"
    assert len(body["daily"]) == 7
    by_date = {point["date"]: point for point in body["daily"]}
    key_yesterday = (now.astimezone(TZ) - timedelta(days=1)).date().isoformat()
    key_two_days_ago = (now.astimezone(TZ) - timedelta(days=2)).date().isoformat()
    assert by_date[key_yesterday]["logins"] == 2
    assert by_date[key_yesterday]["login_users"] == 1
    assert by_date[key_yesterday]["registrations"] == 1
    assert by_date[key_two_days_ago]["logins"] == 1
    assert by_date[key_two_days_ago]["login_users"] == 1
    assert by_date[key_two_days_ago]["registrations"] == 1
    # 补零：五天前没有任何事件，保持 0。
    key_five_days_ago = (now.astimezone(TZ) - timedelta(days=5)).date().isoformat()
    assert by_date[key_five_days_ago]["logins"] == 0
    assert by_date[key_five_days_ago]["login_users"] == 0
    assert by_date[key_five_days_ago]["registrations"] == 0

    methods = {item["method"]: item["count"] for item in body["auth_methods"]}
    # 管理员登录的会话也是 password；未知 sso 兜底保留。
    assert methods["password"] == 2
    assert methods["totp"] == 1
    assert methods["email_otp"] == 0
    assert methods["recovery"] == 0
    assert methods["sso"] == 1


def test_admin_stats_regions_top_and_other(client, db_session, monkeypatch) -> None:
    from app.services import geoip

    fake = {
        "1.1.1.1": "广东省 深圳市",
        "8.8.8.8": "United States",
        "127.0.0.1": "内网地址",
    }
    monkeypatch.setattr(geoip, "resolver_ready", lambda: True)
    monkeypatch.setattr(geoip, "describe_ip", lambda ip: fake.get(ip, "内网地址"))
    now = datetime.now(timezone.utc)
    u1 = make_user(db_session, "u1@example.com")
    db_session.add_all(
        [
            AuditLog(
                actor_type="user",
                actor_id=str(u1.id),
                action="login",
                category="auth",
                ip="1.1.1.1",
                created_at=now - timedelta(hours=1),
            ),
            AuditLog(
                actor_type="user",
                actor_id=str(u1.id),
                action="login",
                category="auth",
                ip="1.1.1.1",
                created_at=now - timedelta(hours=2),
            ),
            AuditLog(
                actor_type="user",
                actor_id=str(u1.id),
                action="2fa_login",
                category="auth",
                ip="8.8.8.8",
                created_at=now - timedelta(hours=3),
            ),
        ]
    )
    db_session.commit()
    login_admin(client, db_session)
    regions = client.get("/api/v1/admin/stats?days=7").json()["regions"]
    assert regions[0] == {"region": "广东省 深圳市", "count": 2}
    assert {item["region"]: item["count"] for item in regions} == {
        "广东省 深圳市": 2,
        "United States": 1,
        "内网地址": 1,
    }


def test_admin_stats_regions_empty_without_db(client, db_session, monkeypatch) -> None:
    from app.services import geoip

    monkeypatch.setattr(geoip, "resolver_ready", lambda: False)
    login_admin(client, db_session)
    assert client.get("/api/v1/admin/stats?days=7").json()["regions"] == []
