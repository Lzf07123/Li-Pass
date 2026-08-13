from datetime import datetime, timezone

from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent


def test_create_oauth_models(db_session) -> None:
    user = User(email="u@example.com", password_hash="x", nickname="U")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    client = OAuthClient(
        client_id="cli_test",
        client_secret_hash="secret-hash",
        name="Demo Site",
        redirect_uris=["http://localhost:3001/callback"],
    )
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    assert client.is_active is True
    assert "openid" in client.scopes
    assert client.id is not None

    code = AuthorizationCode(
        code_hash="code-hash",
        client_id=client.id,
        user_id=user.id,
        redirect_uri="http://localhost:3001/callback",
        scope="openid",
        expires_at=datetime.now(timezone.utc),
    )
    db_session.add(code)
    db_session.commit()
    assert code.id is not None

    consent = UserConsent(user_id=user.id, client_id=client.id, scopes=["openid"])
    db_session.add(consent)
    db_session.commit()
    assert consent.id is not None
