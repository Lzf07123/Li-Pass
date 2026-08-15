from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.trusted_device import TrustedDevice
from app.models.user import User
from app.security.tokens import hash_token
from app.services.trusted_devices import TRUSTED_DEVICE_COOKIE
from tests.helpers import register_and_login


def _add_device(db_session, user, token: str) -> TrustedDevice:
    device = TrustedDevice(
        user_id=user.id,
        token_hash=hash_token(token),
        device_name="Test Device",
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(device)
    db_session.commit()
    return device


def test_list_and_revoke_trusted_devices(client, db_session, captured_email) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    token = "device-token-1"
    device = _add_device(db_session, user, token)
    client.cookies.set(
        TRUSTED_DEVICE_COOKIE, token, domain="testserver.local"
    )

    listed = client.get("/api/v1/me/trusted-devices").json()
    assert len(listed) == 1
    assert listed[0]["id"] == str(device.id)
    assert listed[0]["current"] is True

    response = client.delete(f"/api/v1/me/trusted-devices/{device.id}")
    assert response.status_code == 204
    assert client.cookies.get(TRUSTED_DEVICE_COOKIE) is None
    assert client.get("/api/v1/me/trusted-devices").json() == []
    actions = set(db_session.scalars(select(AuditLog.action)).all())
    assert "trusted_device_revoked" in actions


def test_revoke_trusted_device_of_other_user_returns_404(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    db_session.add(
        User(
            email="other@example.com",
            password_hash="x",
            nickname="Other",
        )
    )
    db_session.commit()
    other = db_session.scalar(
        select(User).where(User.email == "other@example.com")
    )
    other_device = _add_device(db_session, other, "other-token")
    response = client.delete(f"/api/v1/me/trusted-devices/{other_device.id}")
    assert response.status_code == 404
    assert db_session.get(TrustedDevice, other_device.id) is not None


def test_password_change_revokes_all_trusted_devices(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    _add_device(db_session, user, "token-a")
    _add_device(db_session, user, "token-b")

    response = client.post(
        "/api/v1/me/password",
        json={
            "current_password": "password123",
            "new_password": "new-password123",
        },
    )
    assert response.status_code == 200
    assert client.get("/api/v1/me/trusted-devices").json() == []


def test_revoke_all_sessions_revokes_all_trusted_devices(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    _add_device(db_session, user, "token-a")
    _add_device(db_session, user, "token-b")

    response = client.post("/api/v1/sessions/revoke-all")
    assert response.status_code == 200
    assert client.get("/api/v1/me/trusted-devices").json() == []
