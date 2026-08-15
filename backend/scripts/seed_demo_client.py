import os

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.oauth_client import OAuthClient

CLIENT_ID = os.environ.get("DEMO_CLIENT_ID", "demo-site")
REDIRECT_URI = os.environ.get(
    "DEMO_REDIRECT_URI", "http://localhost/demo/callback"
)
HOME_URL = os.environ.get("DEMO_HOME_URL", "http://localhost/demo/")
LOGOUT_URI = os.environ.get("DEMO_LOGOUT_URI", "http://localhost/demo/logout")
BACKCHANNEL_LOGOUT_URI = os.environ.get(
    "DEMO_BACKCHANNEL_LOGOUT_URI", "http://demo-site:3001/backchannel-logout"
)


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
                home_url=HOME_URL,
                logout_uri=LOGOUT_URI,
                post_logout_redirect_uris=[HOME_URL],
                backchannel_logout_uri=BACKCHANNEL_LOGOUT_URI,
                redirect_uris=[REDIRECT_URI],
                scopes=["openid", "profile", "email"],
            )
            db.add(client)
        else:
            client.redirect_uris = [REDIRECT_URI]
            client.home_url = HOME_URL
            client.logout_uri = LOGOUT_URI
            client.post_logout_redirect_uris = [HOME_URL]
            client.backchannel_logout_uri = BACKCHANNEL_LOGOUT_URI
            client.is_active = True
        db.commit()
    print(f"示例客户端就绪: client_id={CLIENT_ID}（公开客户端，无 secret）")


if __name__ == "__main__":
    main()
