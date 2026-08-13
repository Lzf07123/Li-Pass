import pytest

from app.core.config import Settings


def _prod_env(**overrides: str) -> dict[str, str]:
    env = {
        "ENVIRONMENT": "production",
        "JWT_ISSUER": "https://auth.example.com",
        "FRONTEND_BASE_URL": "https://portal.example.com",
        "DATABASE_URL": (
            "postgresql+psycopg://portal:Str0ng-DB-Pass-123@db.example.com:5432/portal"
        ),
        "REDIS_URL": (
            "redis://:Str0ng-Redis-Pass-123@redis.example.com:6379/0"
        ),
        "CORS_ORIGINS": '["https://portal.example.com"]',
        "ALLOWED_HOSTS": '["portal.example.com","api.portal.example.com"]',
        "SESSION_COOKIE_SECURE": "true",
        "SESSION_COOKIE_SAMESITE": "lax",
        "EMAIL_BACKEND": "smtp",
        "SMTP_HOST": "smtp.example.com",
        "SMTP_FROM": "noreply@example.com",
        "PENDING_REQUEST_STORE": "redis",
        "TWOFA_STORE": "redis",
        "RATE_LIMITER": "redis",
        "JWT_PRIVATE_KEY_PATH": "/app/keys/jwt_private.pem",
        "ENCRYPTION_KEY_PATH": "/app/keys/encryption.key",
    }
    env.update(overrides)
    return env


def _settings(monkeypatch, **overrides: str) -> Settings:
    for key, value in _prod_env(**overrides).items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_valid_production_settings_ok(monkeypatch) -> None:
    settings = _settings(monkeypatch)
    assert settings.environment == "production"
    assert settings.session_cookie_secure is True


def test_unknown_environment_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="ENVIRONMENT"):
        _settings(monkeypatch, ENVIRONMENT="prod")


def test_notification_settings_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_NOTIFICATION_RATE_LIMIT", raising=False)
    monkeypatch.delenv("ADMIN_NOTIFICATION_RATE_WINDOW_SECONDS", raising=False)
    monkeypatch.delenv("NOTIFICATION_MAX_RECIPIENTS", raising=False)
    monkeypatch.delenv("NOTIFICATION_RETENTION_DAYS", raising=False)
    settings = Settings(_env_file=None)
    assert settings.admin_notification_rate_limit == 20
    assert settings.admin_notification_rate_window_seconds == 3600
    assert settings.notification_max_recipients == 500
    assert settings.notification_retention_days == 180


def test_notification_settings_reject_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("NOTIFICATION_MAX_RECIPIENTS", "0")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_invalid_samesite_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="SESSION_COOKIE_SAMESITE"):
        _settings(monkeypatch, SESSION_COOKIE_SAMESITE="weird")


def test_invalid_email_backend_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="EMAIL_BACKEND"):
        _settings(monkeypatch, EMAIL_BACKEND="sendgrid")


def test_production_localhost_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="jwt_issuer"):
        _settings(monkeypatch, JWT_ISSUER="http://localhost:8000")


def test_production_relative_key_path_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="绝对路径"):
        _settings(monkeypatch, JWT_PRIVATE_KEY_PATH="jwt_private.pem")


def test_production_weak_redis_password_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="Redis"):
        _settings(monkeypatch, REDIS_URL="redis://:short@redis.example.com:6379/0")


def test_production_localhost_allowed_hosts_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
        _settings(monkeypatch, ALLOWED_HOSTS='["localhost"]')


def test_production_allowed_hosts_keeps_loopback_for_healthcheck(monkeypatch) -> None:
    settings = _settings(
        monkeypatch, ALLOWED_HOSTS='["portal.example.com","127.0.0.1"]'
    )
    assert settings.allowed_hosts == ["portal.example.com", "127.0.0.1"]


def test_production_console_email_rejected(monkeypatch) -> None:
    with pytest.raises(ValueError, match="SMTP"):
        _settings(monkeypatch, EMAIL_BACKEND="console")


def test_session_default_ttl_must_not_exceed_remember_ttl(monkeypatch) -> None:
    with pytest.raises(ValueError, match="SESSION_DEFAULT_TTL_DAYS"):
        _settings(
            monkeypatch,
            ENVIRONMENT="development",
            SESSION_DEFAULT_TTL_DAYS="31",
        )
