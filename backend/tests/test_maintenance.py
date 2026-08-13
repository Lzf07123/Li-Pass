from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.otp import Otp, OtpPurpose
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.maintenance import cleanup_expired_ephemeral_rows


def test_cleanup_removes_only_expired_rows_beyond_retention(db_session) -> None:
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=30)
    fresh = now + timedelta(minutes=5)
    user = User(email="cleanup@example.com", password_hash="x", nickname="Cleanup")
    client = OAuthClient(client_id="cleanup-client", name="Cleanup Client")
    db_session.add_all([user, client])
    db_session.flush()

    db_session.add_all(
        [
            Otp(
                purpose=OtpPurpose.register,
                target="old@example.com",
                code_hash="a" * 64,
                expires_at=old,
            ),
            Otp(
                purpose=OtpPurpose.register,
                target="fresh@example.com",
                code_hash="b" * 64,
                expires_at=fresh,
            ),
            AuthorizationCode(
                code_hash="c" * 64,
                client_id=client.id,
                user_id=user.id,
                redirect_uri="https://app.example.com/callback",
                scope="openid",
                expires_at=old,
            ),
            AuthorizationCode(
                code_hash="d" * 64,
                client_id=client.id,
                user_id=user.id,
                redirect_uri="https://app.example.com/callback",
                scope="openid",
                expires_at=fresh,
            ),
            AccountInvite(
                email="old-invite@example.com",
                token_hash="e" * 64,
                expires_at=old,
            ),
            AccountInvite(
                email="fresh-invite@example.com",
                token_hash="f" * 64,
                expires_at=fresh,
            ),
        ]
    )
    db_session.commit()

    counts = cleanup_expired_ephemeral_rows(db_session)

    assert counts["otps"] == 1
    assert counts["authorization_codes"] == 1
    assert counts["account_invites"] == 1
    remaining_otps = db_session.scalars(select(Otp)).all()
    remaining_codes = db_session.scalars(select(AuthorizationCode)).all()
    remaining_invites = db_session.scalars(select(AccountInvite)).all()
    assert [otp.target for otp in remaining_otps] == ["fresh@example.com"]
    assert [code.code_hash for code in remaining_codes] == ["d" * 64]
    assert [inv.email for inv in remaining_invites] == ["fresh-invite@example.com"]


def test_cleanup_removes_audit_logs_beyond_retention(
    db_session, monkeypatch
) -> None:
    from app.core.config import Settings

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=200)
    fresh = now - timedelta(days=1)
    db_session.add_all(
        [
            AuditLog(
                actor_type="user",
                actor_id="u1",
                action="login",
                category="auth",
                created_at=old,
            ),
            AuditLog(
                actor_type="user",
                actor_id="u2",
                action="login",
                category="auth",
                created_at=fresh,
            ),
        ]
    )
    db_session.commit()
    settings = Settings(_env_file=None, audit_retention_days=180)
    monkeypatch.setattr(
        "app.services.maintenance.get_settings", lambda: settings
    )

    counts = cleanup_expired_ephemeral_rows(db_session)

    assert counts["audit_logs"] == 1
    remaining = db_session.scalars(select(AuditLog)).all()
    assert [row.actor_id for row in remaining] == ["u2"]


def test_cleanup_removes_stale_sessions(db_session, monkeypatch) -> None:
    from app.core.config import Settings

    now = datetime.now(timezone.utc)
    user = User(
        email="session-cleanup@example.com",
        password_hash="x",
        nickname="S",
    )
    db_session.add(user)
    db_session.flush()
    db_session.add_all(
        [
            # 活跃会话：保留。
            SessionModel(
                user_id=user.id,
                token_hash="a" * 64,
                expires_at=now + timedelta(days=1),
                last_used_at=now,
            ),
            # 31 天前吊销：删除。
            SessionModel(
                user_id=user.id,
                token_hash="b" * 64,
                expires_at=now + timedelta(days=1),
                last_used_at=now,
                revoked_at=now - timedelta(days=31),
            ),
            # 40 天前已过期但从未吊销的僵尸会话：删除。
            SessionModel(
                user_id=user.id,
                token_hash="c" * 64,
                expires_at=now - timedelta(days=40),
                last_used_at=now - timedelta(days=40),
            ),
            # 1 天前吊销：仍在保留期内，保留。
            SessionModel(
                user_id=user.id,
                token_hash="d" * 64,
                expires_at=now + timedelta(days=1),
                last_used_at=now,
                revoked_at=now - timedelta(days=1),
            ),
        ]
    )
    db_session.commit()
    settings = Settings(_env_file=None, session_retention_days=30)
    monkeypatch.setattr(
        "app.services.maintenance.get_settings", lambda: settings
    )

    counts = cleanup_expired_ephemeral_rows(db_session)

    assert counts["sessions"] == 2
    remaining = db_session.scalars(select(SessionModel)).all()
    assert {row.token_hash for row in remaining} == {"a" * 64, "d" * 64}
