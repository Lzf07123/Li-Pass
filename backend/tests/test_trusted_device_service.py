from datetime import datetime, timedelta, timezone

from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.models.trusted_device import TrustedDevice
from app.models.user import User
from app.services import trusted_devices
from app.services.trusted_devices import (
    TRUSTED_DEVICE_COOKIE,
    find_valid,
    grant,
    revoke_all,
    revoke_one,
)


def _request() -> Request:
    return Request(
        scope={
            "type": "http",
            "headers": [(b"user-agent", b"TestBrowser/1.0")],
            "client": ("127.0.0.1", 1234),
        }
    )


def _cookie_token(response: Response) -> str:
    header = response.headers.get("set-cookie", "")
    assert TRUSTED_DEVICE_COOKIE in header
    return header.split(f"{TRUSTED_DEVICE_COOKIE}=", 1)[1].split(";", 1)[0]


def test_grant_and_find_valid(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    response = Response()
    device = grant(db_session, user.id, _request(), response)
    assert device.user_id == user.id
    raw_token = _cookie_token(response)

    found = find_valid(db_session, user.id, raw_token)
    assert found is not None and found.id == device.id
    assert found.last_used_at is not None


def test_find_valid_rejects_other_user_and_garbage(db_session) -> None:
    alice = User(email="a@example.com", password_hash="x", nickname="A")
    bob = User(email="b@example.com", password_hash="x", nickname="B")
    db_session.add_all([alice, bob])
    db_session.commit()
    response = Response()
    grant(db_session, alice.id, _request(), response)
    token = _cookie_token(response)

    assert find_valid(db_session, bob.id, token) is None
    assert find_valid(db_session, alice.id, "garbage") is None
    assert find_valid(db_session, alice.id, None) is None


def test_find_valid_rejects_expired_or_revoked(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    response = Response()
    grant(db_session, user.id, _request(), response)
    token = _cookie_token(response)
    device = find_valid(db_session, user.id, token)
    device.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert find_valid(db_session, user.id, token) is None

    response2 = Response()
    device2 = grant(db_session, user.id, _request(), response2)
    token2 = _cookie_token(response2)
    revoke_one(db_session, user.id, device2.id)
    assert find_valid(db_session, user.id, token2) is None


def test_revoke_one_and_all(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    device = TrustedDevice(
        user_id=user.id,
        token_hash="a" * 64,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(device)
    db_session.commit()

    other = User(email="o@example.com", password_hash="x", nickname="O")
    db_session.add(other)
    db_session.commit()
    assert revoke_one(db_session, other.id, device.id) is None
    revoked = revoke_one(db_session, user.id, device.id)
    assert revoked is not None and revoked.revoked_at is not None
    assert revoke_one(db_session, user.id, device.id) is None

    db_session.add(
        TrustedDevice(
            user_id=user.id,
            token_hash="b" * 64,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
    )
    db_session.commit()
    assert revoke_all(db_session, user.id) == 1
    assert revoke_all(db_session, user.id) == 0


def test_trusted_device_ttl_default() -> None:
    assert Settings(_env_file=None).trusted_device_ttl_days == 7
    assert trusted_devices.get_settings().trusted_device_ttl_days == 7
