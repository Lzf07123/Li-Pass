from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_token


def _login_admin(client, db_session) -> User:
    admin = User(
        email="admin@example.com",
        password_hash=hash_password("password123"),
        nickname="Admin",
        role=UserRole.admin,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )
    return admin


def _make_user(db_session, email: str = "target@example.com") -> User:
    user = User(
        email=email,
        password_hash=hash_password("oldpass123"),
        nickname="Target",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _grant_window(client) -> None:
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )


def test_admin_reset_password_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)
    _grant_window(client)

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        json={"new_password": "newpass123"},
    )
    assert response.status_code == 200


def test_admin_reset_twofa_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)
    _grant_window(client)
    assert client.post(
        f"/api/v1/admin/users/{user.id}/reset-2fa", json={}
    ).status_code == 200


def test_admin_role_promotion_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)
    _grant_window(client)
    response = client.patch(
        f"/api/v1/admin/users/{user.id}", json={"role": "admin"}
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


def test_admin_batch_delete_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    bob = _make_user(db_session, "bob@example.com")
    carol = _make_user(db_session, "carol@example.com")
    _grant_window(client)

    response = client.post(
        "/api/v1/admin/users/batch/delete",
        json={"user_ids": [str(bob.id), str(carol.id)]},
    )
    assert response.status_code == 200


def test_admin_delete_user_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)
    _grant_window(client)
    assert client.post(
        f"/api/v1/admin/users/{user.id}/delete", json={}
    ).status_code == 200


def test_admin_delete_client_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    client_model = OAuthClient(
        client_id="cli_del", name="Del", redirect_uris=["http://x/cb"]
    )
    db_session.add(client_model)
    db_session.commit()
    _grant_window(client)

    response = client.request(
        "DELETE", f"/api/v1/admin/clients/{client_model.id}", json={}
    )
    assert response.status_code == 204


def test_admin_reset_secret_without_password_in_window(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    client_model = OAuthClient(
        client_id="cli_secret",
        client_secret_hash=hash_token("old-secret"),
        name="Secret",
        redirect_uris=["http://x/cb"],
    )
    db_session.add(client_model)
    db_session.commit()
    _grant_window(client)

    response = client.post(
        f"/api/v1/admin/clients/{client_model.id}/reset-secret", json={}
    )
    assert response.status_code == 200
