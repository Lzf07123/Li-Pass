from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User
from app.services.federated_logout import (
    revoke_session_links,
    revoke_user_links,
)


def _make_session(db_session, user, suffix: str) -> SessionModel:
    session = SessionModel(
        user_id=user.id,
        token_hash=f"hash-{suffix}",
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )
    db_session.add(session)
    db_session.commit()
    return session


def test_revoke_session_links_scoped_and_idempotent(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    client = OAuthClient(client_id="cli", name="C", redirect_uris=["http://x/cb"])
    db_session.add_all([user, client])
    db_session.commit()
    s1 = _make_session(db_session, user, "1")
    s2 = _make_session(db_session, user, "2")
    for session in (s1, s2):
        db_session.add(
            OIDCClientSession(
                session_id=session.id, client_id=client.id, user_id=user.id
            )
        )
    db_session.commit()

    assert revoke_session_links(db_session, [s1.id]) == 1
    assert revoke_session_links(db_session, [s1.id]) == 0
    links = db_session.scalars(select(OIDCClientSession)).all()
    by_session = {str(link.session_id): link for link in links}
    assert by_session[str(s1.id)].revoked_at is not None
    assert by_session[str(s2.id)].revoked_at is None


def test_revoke_user_links_revokes_all(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    other = User(email="o@example.com", password_hash="x", nickname="O")
    client = OAuthClient(client_id="cli", name="C", redirect_uris=["http://x/cb"])
    db_session.add_all([user, other, client])
    db_session.commit()
    s1 = _make_session(db_session, user, "1")
    s2 = _make_session(db_session, other, "2")
    for user_id, session in ((user.id, s1), (other.id, s2)):
        db_session.add(
            OIDCClientSession(
                session_id=session.id, client_id=client.id, user_id=user_id
            )
        )
    db_session.commit()

    assert revoke_user_links(db_session, user.id) == 1
    links = db_session.scalars(select(OIDCClientSession)).all()
    by_user = {link.user_id: link for link in links}
    assert by_user[user.id].revoked_at is not None
    assert by_user[other.id].revoked_at is None
