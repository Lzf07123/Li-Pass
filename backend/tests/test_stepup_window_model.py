import pytest

from app.core.config import Settings
from app.models.session import Session


def test_session_model_has_stepup_at_column() -> None:
    assert "stepup_at" in Session.__table__.columns
    column = Session.__table__.columns["stepup_at"]
    assert column.nullable is True


def test_stepup_settings_defaults(monkeypatch) -> None:
    for var in (
        "STEPUP_WINDOW_MINUTES",
        "STEPUP_RATE_LIMIT",
        "STEPUP_RATE_WINDOW_SECONDS",
        "STEPUP_EMAIL_RATE_LIMIT",
        "STEPUP_EMAIL_RATE_WINDOW_SECONDS",
    ):
        monkeypatch.delenv(var, raising=False)
    settings = Settings(_env_file=None)
    assert settings.stepup_window_minutes == 30
    assert settings.stepup_rate_limit == 5
    assert settings.stepup_rate_window_seconds == 900
    assert settings.stepup_email_rate_limit == 10
    assert settings.stepup_email_rate_window_seconds == 900


def test_stepup_settings_accept_zero_window(monkeypatch) -> None:
    monkeypatch.setenv("STEPUP_WINDOW_MINUTES", "0")
    settings = Settings(_env_file=None)
    assert settings.stepup_window_minutes == 0


def test_stepup_settings_reject_invalid_values(monkeypatch) -> None:
    monkeypatch.setenv("STEPUP_WINDOW_MINUTES", "-1")
    with pytest.raises(ValueError, match="STEPUP_WINDOW_MINUTES"):
        Settings(_env_file=None)

    monkeypatch.setenv("STEPUP_WINDOW_MINUTES", "30")
    monkeypatch.setenv("STEPUP_RATE_LIMIT", "0")
    with pytest.raises(ValueError, match="STEPUP_RATE_LIMIT"):
        Settings(_env_file=None)

    monkeypatch.setenv("STEPUP_RATE_LIMIT", "5")
    monkeypatch.setenv("STEPUP_RATE_WINDOW_SECONDS", "0")
    with pytest.raises(ValueError, match="STEPUP_RATE_WINDOW_SECONDS"):
        Settings(_env_file=None)

    monkeypatch.setenv("STEPUP_RATE_WINDOW_SECONDS", "900")
    monkeypatch.setenv("STEPUP_EMAIL_RATE_LIMIT", "0")
    with pytest.raises(ValueError, match="STEPUP_EMAIL_RATE_LIMIT"):
        Settings(_env_file=None)

    monkeypatch.setenv("STEPUP_EMAIL_RATE_LIMIT", "10")
    monkeypatch.setenv("STEPUP_EMAIL_RATE_WINDOW_SECONDS", "0")
    with pytest.raises(ValueError, match="STEPUP_EMAIL_RATE_WINDOW_SECONDS"):
        Settings(_env_file=None)
