"""审计日志展示增强：分类/动作中文标签与操作者可读性。"""

from app.models.oauth_client import OAuthClient
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from app.services.audit import log_audit


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


def _make_user(db_session, email: str, nickname: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        nickname=nickname,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_client(db_session) -> OAuthClient:
    client = OAuthClient(
        client_id="demo-site",
        name="Demo Site",
        redirect_uris=["https://demo.example.com/callback"],
    )
    db_session.add(client)
    db_session.commit()
    return client


def test_audit_list_returns_labels_and_readable_actor(
    client, db_session
) -> None:
    admin = _login_admin(client, db_session)
    alice = _make_user(db_session, "alice@example.com", "Alice")
    demo = _make_client(db_session)

    log_audit(db_session, "user", str(alice.id), "login", category="auth")
    log_audit(
        db_session,
        "admin",
        str(admin.id),
        "admin_update_user",
        category="admin_user",
    )
    log_audit(
        db_session,
        "client",
        demo.client_id,
        "block_add",
        category="admin_block",
    )
    log_audit(
        db_session,
        "system",
        None,
        "rate_limit_rejected",
        category="security",
    )
    log_audit(
        db_session,
        "user",
        str(alice.id),
        "future_new_action",
        category="auth",
    )

    items = client.get("/api/v1/admin/audit-logs?limit=20").json()
    by_action = {item["action"]: item for item in items}

    login = by_action["login"]
    assert login["category_label"] == "认证"
    assert login["action_label"] == "登录"
    assert login["actor"] == {
        "type": "user",
        "type_label": "用户",
        "id": str(alice.id),
        "display": "Alice · alice@example.com",
    }

    admin_row = by_action["admin_update_user"]
    assert admin_row["actor"]["type_label"] == "管理员"
    assert admin_row["actor"]["display"] == "Admin · admin@example.com"
    assert admin_row["category_label"] == "用户管理"
    assert admin_row["action_label"] == "更新用户"

    client_row = by_action["block_add"]
    assert client_row["actor"]["type_label"] == "授权网站"
    assert client_row["actor"]["display"] == "Demo Site"

    system_row = by_action["rate_limit_rejected"]
    assert system_row["actor"]["type_label"] == "系统"
    assert system_row["actor"]["display"] == ""
    assert system_row["action_label"] == "限流拦截"

    # 未知动作原样回退，不因缺少标签而丢失记录。
    unknown = by_action["future_new_action"]
    assert unknown["action_label"] == "future_new_action"
