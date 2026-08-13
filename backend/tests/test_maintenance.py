from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.account_invite import AccountInvite
from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.otp import Otp, OtpPurpose
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
