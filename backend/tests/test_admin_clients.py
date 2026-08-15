from sqlalchemy import select

from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.security.tokens import hash_token


def login_as(client, email: str, password: str = "password123"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


def test_admin_required(client, db_session) -> None:
    db_session.add(
        User(
            email="u@example.com",
            password_hash=hash_password("password123"),
            nickname="U",
            role=UserRole.user,
        )
    )
    db_session.commit()
    assert login_as(client, "u@example.com").status_code == 200
    response = client.get("/api/v1/admin/clients")
    assert response.status_code == 403


def test_admin_rejects_unsafe_backchannel_url_on_create(
    client, db_session, monkeypatch
) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")

    class _ProdSettings:
        environment = "production"

    monkeypatch.setattr("app.schemas.oauth.get_settings", lambda: _ProdSettings())
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings", lambda: _ProdSettings()
    )
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Bad",
            "redirect_uris": ["https://rp.example/cb"],
            "backchannel_logout_uri": "https://127.0.0.1/logout",
        },
    )
    assert response.status_code == 400


def test_admin_rejects_unsafe_backchannel_url_on_update(
    client, db_session, monkeypatch
) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")

    class _ProdSettings:
        environment = "production"

    monkeypatch.setattr("app.schemas.oauth.get_settings", lambda: _ProdSettings())
    monkeypatch.setattr(
        "app.services.federated_logout.get_settings", lambda: _ProdSettings()
    )
    created = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Ok",
            "redirect_uris": ["https://rp.example/cb"],
            "backchannel_logout_uri": "https://93.184.216.34/logout",
        },
    )
    assert created.status_code == 200
    client_id = created.json()["client"]["id"]
    response = client.patch(
        f"/api/v1/admin/clients/{client_id}",
        json={"backchannel_logout_uri": "https://127.0.0.1/logout"},
    )
    assert response.status_code == 400


def test_admin_create_and_reset_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    assert login_as(client, "a@example.com").status_code == 200

    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Demo",
            "redirect_uris": ["http://localhost:3001/callback"],
            "public": False,
        },
    )
    assert response.status_code == 200
    body = response.json()
    secret = body["client_secret"]
    assert secret
    assert body["client"]["has_secret"] is True
    stored = db_session.scalar(
        select(OAuthClient).where(OAuthClient.client_id == body["client"]["client_id"])
    )
    assert stored is not None
    assert stored.client_secret_hash == hash_token(secret)

    response = client.post(
        f"/api/v1/admin/clients/{body['client']['id']}/reset-secret",
        json={"current_password": "password123"},
    )
    assert response.status_code == 200
    new_secret = response.json()["client_secret"]
    assert new_secret != secret


def test_public_client_has_no_secret(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "SPA",
            "redirect_uris": ["http://localhost:5173/callback"],
            "public": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["client_secret"] is None
    assert response.json()["client"]["has_secret"] is False


def test_admin_delete_client(client, db_session) -> None:
    db_session.add(
        User(
            email="admin@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "password123"},
    )

    created = client.post(
        "/api/v1/admin/clients",
        json={"name": "ToDelete", "redirect_uris": ["http://x/cb"]},
    ).json()["client"]

    response = client.request(
        "DELETE",
        f"/api/v1/admin/clients/{created['id']}",
        json={"current_password": "password123"},
    )
    assert response.status_code == 204
    remaining = client.get("/api/v1/admin/clients").json()
    assert all(item["client_id"] != created["client_id"] for item in remaining)


def test_client_url_scheme_validation(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")

    # javascript:/data:/file: 等危险 scheme 一律拒绝
    for bad in (
        "javascript:alert(1)",
        "data:text/html,<script>1</script>",
        "file:///etc/passwd",
    ):
        response = client.post(
            "/api/v1/admin/clients",
            json={"name": "Bad", "redirect_uris": [bad]},
        )
        assert response.status_code == 422, bad

    # home_url/logout_uri 同样拒绝非 http/https
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Bad",
            "redirect_uris": ["http://ok.example/cb"],
            "home_url": "javascript:alert(1)",
        },
    )
    assert response.status_code == 422

    # 重复回调地址拒绝
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Dup",
            "redirect_uris": ["http://ok.example/cb", "http://ok.example/cb"],
        },
    )
    assert response.status_code == 422

    # 合法 http(s) 地址放行
    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "OK",
            "redirect_uris": ["http://ok.example/cb?from=1"],
            "home_url": "https://ok.example",
        },
    )
    assert response.status_code == 200


def test_client_lifecycle_audited(client, db_session) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")

    created = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Audited",
            "redirect_uris": ["http://ok.example/cb"],
            "public": False,
        },
    ).json()["client"]
    client.patch(
        f"/api/v1/admin/clients/{created['id']}",
        json={"name": "Audited2"},
    )
    client.post(
        f"/api/v1/admin/clients/{created['id']}/reset-secret",
        json={"current_password": "password123"},
    )
    client.request(
        "DELETE",
        f"/api/v1/admin/clients/{created['id']}",
        json={"current_password": "password123"},
    )

    logs = client.get("/api/v1/admin/audit-logs").json()
    actions = {log["action"] for log in logs}
    assert {
        "admin_create_client",
        "admin_update_client",
        "admin_reset_client_secret",
        "admin_delete_client",
    } <= actions


def test_client_url_https_required_in_production(
    client, db_session, monkeypatch
) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
            role=UserRole.admin,
        )
    )
    db_session.commit()
    login_as(client, "a@example.com")

    class _ProdSettings:
        environment = "production"

    monkeypatch.setattr("app.schemas.oauth.get_settings", lambda: _ProdSettings())

    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Http",
            "redirect_uris": ["http://ok.example/cb"],
        },
    )
    assert response.status_code == 422

    response = client.post(
        "/api/v1/admin/clients",
        json={
            "name": "Https",
            "redirect_uris": ["https://ok.example/cb"],
            "home_url": "https://ok.example",
            "logo_url": "https://ok.example/logo.png",
            "logout_uri": "https://ok.example/logout",
        },
    )
    assert response.status_code == 200
