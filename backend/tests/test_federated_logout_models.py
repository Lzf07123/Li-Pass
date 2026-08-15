import uuid
from datetime import datetime, timezone

from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
from app.models.user import User


def test_client_logout_fields_defaults(db_session) -> None:
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add(client)
    db_session.commit()
    assert client.post_logout_redirect_uris == []
    assert client.backchannel_logout_uri is None


def test_oidc_client_session_tracks_portal_session(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add_all([user, client])
    db_session.commit()
    portal = SessionModel(
        user_id=user.id,
        token_hash="hash-1",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(portal)
    db_session.commit()
    link = OIDCClientSession(
        session_id=portal.id, client_id=client.id, user_id=user.id
    )
    db_session.add(link)
    db_session.commit()
    assert link.sid == str(portal.id)
    assert link.revoked_at is None
    assert link.created_at is not None


def test_authorization_code_stores_session_id(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    client = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add_all([user, client])
    db_session.commit()
    portal = SessionModel(
        user_id=user.id,
        token_hash="hash-2",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(portal)
    db_session.commit()
    code = AuthorizationCode(
        code_hash="code-hash",
        client_id=client.id,
        user_id=user.id,
        redirect_uri="http://x/cb",
        scope="openid",
        expires_at=datetime.now(timezone.utc),
        session_id=portal.id,
    )
    db_session.add(code)
    db_session.commit()
    assert code.session_id == portal.id


def test_oidc_client_session_sid_is_string_uuid() -> None:
    link = OIDCClientSession(session_id=uuid.uuid4())
    assert link.sid == str(link.session_id)
