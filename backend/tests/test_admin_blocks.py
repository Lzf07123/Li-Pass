from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password


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


def test_admin_blocks_crud(client, db_session) -> None:
    login_admin(client, db_session)
    client_model = OAuthClient(client_id="cli_x", name="X", redirect_uris=["http://x/cb"])
    db_session.add(client_model)
    db_session.commit()
    db_session.refresh(client_model)

    response = client.post(
        f"/api/v1/admin/clients/{client_model.id}/blocks",
        json={"email": "Bad@Example.com", "reason": "滥用"},
    )
    assert response.status_code == 200
    block_id = response.json()["id"]
    assert response.json()["email"] == "bad@example.com"

    assert len(client.get(f"/api/v1/admin/clients/{client_model.id}/blocks").json()) == 1
    assert (
        client.delete(
            f"/api/v1/admin/clients/{client_model.id}/blocks/{block_id}"
        ).status_code
        == 204
    )
