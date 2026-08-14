from app.core.config import Settings
from app.models.user import User
from app.security.passwords import hash_password


def test_login_rate_limit_defaults_tightened() -> None:
    settings = Settings(_env_file=None)
    assert settings.login_rate_limit == 5
    assert settings.login_email_rate_limit == 10
    assert settings.login_ip_rate_limit == 20


def test_login_global_email_rate_limit(
    client, db_session, monkeypatch
) -> None:
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
        )
    )
    db_session.commit()
    settings = Settings(
        _env_file=None,
        login_email_rate_limit=2,
        login_ip_rate_limit=1000,
    )
    monkeypatch.setattr("app.api.routes.auth.settings", settings)

    for _ in range(2):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrong"},
    )
    assert response.status_code == 429


def test_login_pair_rate_limit_blocks_sixth_failed_attempt(
    client, db_session
) -> None:
    """默认阈值下，同一邮箱+IP 第 6 次密码错误必须返回 429，而不是继续 401。"""
    db_session.add(
        User(
            email="a@example.com",
            password_hash=hash_password("password123"),
            nickname="A",
        )
    )
    db_session.commit()

    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "wrong"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "a@example.com", "password": "wrong"},
    )
    assert response.status_code == 429
