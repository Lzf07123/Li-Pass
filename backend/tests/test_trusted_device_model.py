from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.trusted_device import TrustedDevice
from app.models.user import User


def test_trusted_device_fields_and_cascade(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    device = TrustedDevice(
        user_id=user.id,
        token_hash="h" * 64,
        device_name="MacBook Pro",
        user_agent="ua",
        ip="127.0.0.1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(device)
    db_session.commit()
    assert device.created_at is not None
    assert device.revoked_at is None
    assert device.last_used_at is None


def test_trusted_device_token_hash_unique(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    common = {
        "user_id": user.id,
        "token_hash": "dup",
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }
    db_session.add(TrustedDevice(**common))
    db_session.commit()
    db_session.add(TrustedDevice(**common))
    with pytest.raises(IntegrityError):
        db_session.commit()
