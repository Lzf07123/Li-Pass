from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.config import Settings
from app.models.audit_log import AuditLog
from app.models.session import Session as SessionModel
from tests.helpers import register_and_login


def test_stepup_endpoints_require_login(client) -> None:
    assert client.get("/api/v1/me/step-up").status_code == 401
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 401
    )


def test_login_does_not_grant_stepup_window(client, captured_email) -> None:
    register_and_login(client, captured_email)
    status = client.get("/api/v1/me/step-up").json()
    assert status["active"] is False
    assert status["window_minutes"] == 30
    assert status["expires_in_seconds"] == 0


def test_stepup_verify_grants_window(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)

    response = client.post(
        "/api/v1/me/step-up", json={"password": "password123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "身份复核成功"
    assert body["active"] is True
    assert 0 < body["expires_in_seconds"] <= 30 * 60

    status = client.get("/api/v1/me/step-up").json()
    assert status["active"] is True

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "stepup_verify_success")
    ).all()
    assert len(logs) == 1
    assert logs[0].category == "security"


def test_stepup_verify_wrong_password_logs_failure(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)

    response = client.post(
        "/api/v1/me/step-up", json={"password": "wrong-password"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "当前密码错误"

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "stepup_failed")
    ).all()
    assert len(logs) == 1
    assert logs[0].category == "security"


def test_stepup_pair_rate_limit_blocks_sixth_failure(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)

    for _ in range(5):
        response = client.post(
            "/api/v1/me/step-up", json={"password": "wrong-password"}
        )
        assert response.status_code == 400

    response = client.post(
        "/api/v1/me/step-up", json={"password": "wrong-password"}
    )
    assert response.status_code == 429

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "stepup_failed")
    ).all()
    assert len(logs) == 6


def test_stepup_pair_limiter_resets_after_success(
    client, captured_email
) -> None:
    register_and_login(client, captured_email)

    for _ in range(5):
        assert (
            client.post(
                "/api/v1/me/step-up", json={"password": "wrong-password"}
            ).status_code
            == 400
        )
    # 第 6 次为正确密码：仅失败计入按邮箱+IP 的限流，成功应放行并清零计数。
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )


def test_stepup_global_email_rate_limit(
    client, captured_email, monkeypatch
) -> None:
    register_and_login(client, captured_email)
    settings = Settings(
        _env_file=None,
        stepup_email_rate_limit=2,
        stepup_rate_limit=1000,
    )
    monkeypatch.setattr("app.services.stepup.get_settings", lambda: settings)

    for _ in range(2):
        assert (
            client.post(
                "/api/v1/me/step-up", json={"password": "wrong-password"}
            ).status_code
            == 400
        )
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "wrong-password"}
        ).status_code
        == 429
    )


def test_stepup_window_expires(client, captured_email, db_session) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )

    session = db_session.scalar(select(SessionModel))
    session.stepup_at = datetime.now(timezone.utc) - timedelta(minutes=31)
    db_session.commit()

    status = client.get("/api/v1/me/step-up").json()
    assert status["active"] is False
    assert status["expires_in_seconds"] == 0


def test_stepup_window_is_per_session(
    client, captured_email, db_session
) -> None:
    register_and_login(client, captured_email)
    assert (
        client.post(
            "/api/v1/me/step-up", json={"password": "password123"}
        ).status_code
        == 200
    )

    # 登录产生第二个会话：新会话不得继承第一个会话的复核窗口。
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "a@example.com", "password": "password123"},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/me/step-up").json()["active"] is False

    sessions = db_session.scalars(select(SessionModel)).all()
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s.stepup_at is not None) == 1
