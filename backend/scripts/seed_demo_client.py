from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.oauth_client import OAuthClient

CLIENT_ID = "demo-site"
REDIRECT_URI = "http://localhost:3001/callback"


def main() -> None:
    with SessionLocal() as db:
        client = db.scalar(
            select(OAuthClient).where(OAuthClient.client_id == CLIENT_ID)
        )
        if client is None:
            client = OAuthClient(
                client_id=CLIENT_ID,
                name="Demo Site",
                description="OIDC 示例授权网站",
                home_url="http://localhost:3001",
                logout_uri="http://localhost:3001/logout",
                redirect_uris=[REDIRECT_URI],
                scopes=["openid", "profile", "email"],
            )
            db.add(client)
        else:
            client.redirect_uris = [REDIRECT_URI]
            client.home_url = "http://localhost:3001"
            client.logout_uri = "http://localhost:3001/logout"
            client.is_active = True
        db.commit()
    print(f"示例客户端就绪: client_id={CLIENT_ID}（公开客户端，无 secret）")


if __name__ == "__main__":
    main()
