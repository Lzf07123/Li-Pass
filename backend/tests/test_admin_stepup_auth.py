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
    return user


def test_admin_reset_password_requires_current_password(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        json={"new_password": "newpass123"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        json={"new_password": "newpass123", "current_password": "wrong"},
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-password",
        json={"new_password": "newpass123", "current_password": "password123"},
    )
    assert response.status_code == 200


def test_admin_reset_twofa_requires_current_password(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)

    response = client.post(f"/api/v1/admin/users/{user.id}/reset-2fa", json={})
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-2fa",
        json={"current_password": "wrong"},
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/admin/users/{user.id}/reset-2fa",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200


def test_admin_delete_client_requires_current_password(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    client_model = OAuthClient(
        client_id="cli_del", name="Del", redirect_uris=["http://x/cb"]
    )
    db_session.add(client_model)
    db_session.commit()

    response = client.request(
        "DELETE",
        f"/api/v1/admin/clients/{client_model.id}",
        json={"current_password": "wrong"},
    )
    assert response.status_code == 400

    response = client.request(
        "DELETE",
        f"/api/v1/admin/clients/{client_model.id}",
        json={"current_password": "password123"},
    )
    assert response.status_code == 204


def test_admin_reset_secret_requires_current_password(
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

    response = client.post(
        f"/api/v1/admin/clients/{client_model.id}/reset-secret",
        json={"current_password": "wrong"},
    )
    assert response.status_code == 400

    response = client.post(
        f"/api/v1/admin/clients/{client_model.id}/reset-secret",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200


def test_admin_role_promotion_requires_current_password(
    client, db_session
) -> None:
    _login_admin(client, db_session)
    user = _make_user(db_session)

    response = client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"role": "admin"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "需要重新验证密码"

    response = client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"role": "admin", "current_password": "wrong"},
    )
    assert response.status_code == 400

    response = client.patch(
        f"/api/v1/admin/users/{user.id}",
        json={"role": "admin", "current_password": "password123"},
    )
    assert response.status_code == 200
