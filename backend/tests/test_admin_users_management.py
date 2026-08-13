from sqlalchemy import select

from app.models.user import User, UserRole, UserStatus
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


def test_admin_list_and_search_users(client, db_session) -> None:
    login_admin(client, db_session)
    db_session.add(
        User(
            email="bob@example.com",
            password_hash=hash_password("password123"),
            nickname="Bob",
        )
    )
    db_session.commit()

    users = client.get("/api/v1/admin/users").json()
    assert any(user["email"] == "admin@example.com" for user in users)
    assert any(user["email"] == "bob@example.com" for user in users)

    result = client.get("/api/v1/admin/users", params={"q": "bob"}).json()
    assert len(result) == 1
    assert result[0]["email"] == "bob@example.com"


def test_admin_filter_users_by_status_and_role(client, db_session) -> None:
    login_admin(client, db_session)
    db_session.add(
        User(
            email="bob@example.com",
            password_hash=hash_password("password123"),
            nickname="Bob",
            role=UserRole.user,
            status=UserStatus.active,
        )
    )
    db_session.add(
        User(
            email="disabled@example.com",
            password_hash=hash_password("password123"),
            nickname="Disabled",
            role=UserRole.user,
            status=UserStatus.disabled,
        )
    )
    db_session.commit()

    active = client.get(
        "/api/v1/admin/users", params={"status": "active"}
    ).json()
    assert {"admin@example.com", "bob@example.com"} <= {
        user["email"] for user in active
    }
    assert all(user["status"] == "active" for user in active)

    disabled = client.get(
        "/api/v1/admin/users", params={"status": "disabled"}
    ).json()
    assert [user["email"] for user in disabled] == ["disabled@example.com"]

    admins = client.get(
        "/api/v1/admin/users", params={"role": "admin"}
    ).json()
    assert [user["email"] for user in admins] == ["admin@example.com"]
    assert all(user["role"] == "admin" for user in admins)


def test_admin_disable_and_reset_password(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)

    response = client.patch(
        f"/api/v1/admin/users/{bob.id}",
        json={"status": "disabled"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "bob@example.com", "password": "password123"},
        ).status_code
        == 401
    )

    response = client.post(
        f"/api/v1/admin/users/{bob.id}/reset-password",
        json={"new_password": "newpassword456"},
    )
    assert response.status_code == 200
    client.patch(f"/api/v1/admin/users/{bob.id}", json={"status": "active"})
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "bob@example.com", "password": "newpassword456"},
        ).status_code
        == 200
    )


def test_admin_cannot_disable_self(client, db_session) -> None:
    login_admin(client, db_session)
    admin = db_session.scalar(
        select(User).where(User.email == "admin@example.com")
    )
    response = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"status": "disabled"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "不能禁用自己"

    response = client.patch(
        f"/api/v1/admin/users/{admin.id}",
        json={"role": "user"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "不能取消自己的管理员角色"


def test_admin_reset_actions_logged_with_actor(client, db_session) -> None:
    login_admin(client, db_session)
    bob = User(
        email="bob@example.com",
        password_hash=hash_password("password123"),
        nickname="Bob",
    )
    db_session.add(bob)
    db_session.commit()
    db_session.refresh(bob)
    admin = db_session.scalar(
        select(User).where(User.email == "admin@example.com")
    )

    client.post(
        f"/api/v1/admin/users/{bob.id}/reset-password",
        json={"new_password": "newpassword456"},
    )
    client.post(f"/api/v1/admin/users/{bob.id}/reset-2fa")

    logs = client.get("/api/v1/admin/audit-logs").json()
    for action, target_id in (
        ("admin_reset_password", str(bob.id)),
        ("admin_reset_2fa", str(bob.id)),
    ):
        matches = [log for log in logs if log["action"] == action]
        assert matches, f"缺少审计记录: {action}"
        assert matches[0]["actor_id"] == str(admin.id)
        assert matches[0]["target_id"] == target_id
