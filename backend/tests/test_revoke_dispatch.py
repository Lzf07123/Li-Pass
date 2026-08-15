from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User, UserRole
from app.models.user_consent import UserConsent
from app.security.passwords import hash_password
from app.security.tokens import generate_token, hash_token
from tests.helpers import create_client, register_and_login


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


def create_session(db_session, user) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(generate_token()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        last_used_at=datetime.now(timezone.utc),
    )
    db_session.add(session)
    db_session.commit()
    return session


def link(db_session, user, oauth_client, session: SessionModel) -> None:
    db_session.add(
        OIDCClientSession(
            session_id=session.id, client_id=oauth_client.id, user_id=user.id
        )
    )
    db_session.commit()


def test_user_revoke_session_dispatches_backchannel(
    client, db_session, captured_email, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    other_session = create_session(db_session, user)
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    link(db_session, user, oauth_client, other_session)
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.users.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    resp = client.delete(f"/api/v1/sessions/{other_session.id}")
    assert resp.status_code == 204
    assert len(calls) == 1
    assert calls[0][0].sid == str(other_session.id)


def test_admin_batch_revoke_dispatches_backchannel(
    client, db_session, monkeypatch
) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    bob_session = create_session(db_session, bob)
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    link(db_session, bob, oauth_client, bob_session)
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.admin_sessions.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    resp = client.post(
        "/api/v1/admin/sessions/batch-revoke",
        json={"session_ids": [str(bob_session.id)]},
    )
    assert resp.status_code == 200
    assert resp.json()["revoked"] == 1
    assert len(calls) == 1
    assert calls[0][0].sid == str(bob_session.id)


def test_consent_revoke_dispatches_backchannel(
    client, db_session, captured_email, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    portal = db_session.scalar(select(SessionModel))
    oauth_client = create_client(
        db_session,
        client_id="cli_bc",
        redirect_uris=["http://x/cb"],
        backchannel_logout_uri="https://x/backchannel",
    )
    db_session.add(
        UserConsent(
            user_id=user.id, client_id=oauth_client.id, scopes=["openid"]
        )
    )
    db_session.commit()
    link(db_session, user, oauth_client, portal)
    calls: list[list] = []
    monkeypatch.setattr(
        "app.api.routes.users.dispatch_backchannel_logout",
        lambda targets: calls.append(targets) or {},
    )
    resp = client.delete(f"/api/v1/apps/{oauth_client.client_id}")
    assert resp.status_code == 200
    assert resp.json()["backchannel_notified"] is True
    assert resp.json()["logout_uri"] is None
    assert len(calls) == 1
    assert calls[0][0].client_id == "cli_bc"
    # 撤销授权后，该用户在此客户端上的门户会话链接应同步吊销。
    revoked_link = db_session.scalar(
        select(OIDCClientSession).where(
            OIDCClientSession.client_id == oauth_client.id,
        )
    )
    assert revoked_link is not None
    assert revoked_link.revoked_at is not None


def test_consent_revoke_without_logout_channels_returns_false(
    client, db_session, captured_email
) -> None:
    register_and_login(client, captured_email)
    user = db_session.scalar(select(User))
    oauth_client = create_client(
        db_session,
        client_id="cli_none",
        redirect_uris=["http://x/cb"],
    )
    db_session.add(
        UserConsent(
            user_id=user.id, client_id=oauth_client.id, scopes=["openid"]
        )
    )
    db_session.commit()
    resp = client.delete("/api/v1/apps/cli_none")
    assert resp.status_code == 200
    assert resp.json() == {
        "logout_uri": None,
        "backchannel_notified": False,
    }
