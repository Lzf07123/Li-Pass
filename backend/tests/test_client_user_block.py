from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.models.user import User


def test_create_block(db_session) -> None:
    user = User(email="a@example.com", password_hash="x", nickname="A")
    client = OAuthClient(
        client_id="cli_x", name="X", redirect_uris=["http://x/cb"], home_url="http://x"
    )
    db_session.add_all([user, client])
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(client)

    block = ClientUserBlock(
        client_id=client.id, user_id=user.id, email=user.email, reason="滥用"
    )
    db_session.add(block)
    db_session.commit()
    assert block.id is not None
    assert client.home_url == "http://x"
