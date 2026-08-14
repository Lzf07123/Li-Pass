import threading
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.security.passwords import hash_password
from tests.helpers import register_and_login


def _login_admin(client, db_session) -> None:
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


def _isolate_ip2region(tmp_path, monkeypatch) -> None:
    """把数据目录指到空临时目录，避免测试依赖本机真实 xdb 文件。"""
    monkeypatch.setattr(
        get_settings(), "ip2region_data_dir", str(tmp_path / "ip2region")
    )


def test_site_settings_public_registration_switch(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    _isolate_ip2region(tmp_path, monkeypatch)
    _login_admin(client, db_session)

    # 默认跟随环境变量（true）
    settings = client.get("/api/v1/admin/settings").json()
    assert settings["public_registration_enabled"] is True
    assert settings["ip2region"] == {
        "version": None,
        "data_updated_at": None,
        "v4_ready": False,
        "v6_ready": False,
        "auto_update_enabled": False,
        "update_interval_hours": 24,
    }
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }

    # 管理员关闭公开注册
    response = client.put(
        "/api/v1/admin/settings",
        json={"public_registration_enabled": False},
    )
    assert response.status_code == 200
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": False
    }
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "blocked@example.com",
                "password": "password123",
                "nickname": "Blocked",
            },
        ).status_code
        == 403
    )

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_update_site_setting")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["value"] is False

    # 重新开启后恢复公开注册
    assert (
        client.put(
            "/api/v1/admin/settings",
            json={"public_registration_enabled": True},
        ).status_code
        == 200
    )
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }


def test_site_settings_update_without_registration_field(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    """PUT 支持只更新 ip2region 设置，未传的注册开关保持原值（PATCH 语义）。"""
    _isolate_ip2region(tmp_path, monkeypatch)
    _login_admin(client, db_session)

    response = client.put(
        "/api/v1/admin/settings",
        json={"ip2region_auto_update_enabled": True},
    )

    assert response.status_code == 200
    assert response.json()["public_registration_enabled"] is True
    assert client.get("/api/v1/auth/register/status").json() == {
        "public_registration_enabled": True
    }


def test_non_admin_cannot_access_site_settings(
    client, captured_email, tmp_path, monkeypatch
) -> None:
    _isolate_ip2region(tmp_path, monkeypatch)
    register_and_login(client, captured_email)
    assert client.get("/api/v1/admin/settings").status_code == 403
    assert (
        client.put(
            "/api/v1/admin/settings",
            json={"public_registration_enabled": False},
        ).status_code
        == 403
    )


def test_put_ip2region_auto_update_settings(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    _isolate_ip2region(tmp_path, monkeypatch)
    _login_admin(client, db_session)

    response = client.put(
        "/api/v1/admin/settings",
        json={
            "public_registration_enabled": True,
            "ip2region_auto_update_enabled": True,
            "ip2region_update_interval_hours": 48,
        },
    )
    assert response.status_code == 200
    ip2region = response.json()["ip2region"]
    assert ip2region["auto_update_enabled"] is True
    assert ip2region["update_interval_hours"] == 48

    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_update_site_setting")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["ip2region_auto_update_enabled"] is True
    assert logs[0].detail["ip2region_update_interval_hours"] == 48


def _wait_ip2region_status(client, predicate, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        response = client.get("/api/v1/admin/settings/ip2region/update/status")
        assert response.status_code == 200
        body = response.json()
        if predicate(body):
            return body
        time.sleep(0.02)
    raise AssertionError("等待 IP 库更新状态超时")


def test_ip2region_update_runs_in_background_and_completes(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    from app.services import ip2region_update

    _isolate_ip2region(tmp_path, monkeypatch)
    calls = []

    def fake_update(db, actor=None, request=None, on_progress=None):
        calls.append(1)
        if on_progress:
            on_progress("downloading_v4", 100, 200)
            on_progress("downloading_v6", 200, 200)
        return {
            "version": "v9.9.9",
            "data_updated_at": "2026-08-14T00:00:00+00:00",
            "changed": True,
        }

    monkeypatch.setattr(ip2region_update, "update_ip2region", fake_update)
    _login_admin(client, db_session)

    response = client.post("/api/v1/admin/settings/ip2region/update")
    assert response.status_code == 202
    assert response.json()["started"] is True

    body = _wait_ip2region_status(client, lambda s: s["state"] == "success")
    assert body["version"] == "v9.9.9"
    assert body["changed"] is True
    assert calls == [1]


def test_ip2region_update_reports_download_progress(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    from app.services import ip2region_update

    _isolate_ip2region(tmp_path, monkeypatch)
    event = threading.Event()

    def fake_update(db, actor=None, request=None, on_progress=None):
        on_progress("downloading_v4", 100, 200)
        event.wait(5)
        return {
            "version": "v9.9.9",
            "data_updated_at": "2026-08-14T00:00:00+00:00",
            "changed": True,
        }

    monkeypatch.setattr(ip2region_update, "update_ip2region", fake_update)
    _login_admin(client, db_session)

    assert (
        client.post("/api/v1/admin/settings/ip2region/update").status_code
        == 202
    )
    body = _wait_ip2region_status(
        client,
        lambda s: s["stage"] == "downloading_v4" and s["percent"] == 50.0,
    )
    assert body["downloaded_bytes"] == 100
    assert body["total_bytes"] == 200

    event.set()
    _wait_ip2region_status(client, lambda s: s["state"] == "success")


def test_ip2region_update_conflict_returns_409(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    from app.services import ip2region_update

    _isolate_ip2region(tmp_path, monkeypatch)
    event = threading.Event()

    def slow_update(db, actor=None, request=None, on_progress=None):
        event.wait(5)
        return {
            "version": "v9.9.9",
            "data_updated_at": "2026-08-14T00:00:00+00:00",
            "changed": True,
        }

    monkeypatch.setattr(ip2region_update, "update_ip2region", slow_update)
    _login_admin(client, db_session)

    assert (
        client.post("/api/v1/admin/settings/ip2region/update").status_code
        == 202
    )
    assert (
        client.post("/api/v1/admin/settings/ip2region/update").status_code
        == 409
    )

    event.set()
    _wait_ip2region_status(client, lambda s: s["state"] == "success")


def test_ip2region_update_failure_surfaces_status(
    client, db_session, captured_email, tmp_path, monkeypatch
) -> None:
    from app.services import ip2region_update

    _isolate_ip2region(tmp_path, monkeypatch)

    def fail_update(db, actor=None, request=None, on_progress=None):
        raise RuntimeError("版本 v9.9.9 未列入信任清单")

    monkeypatch.setattr(ip2region_update, "update_ip2region", fail_update)
    _login_admin(client, db_session)

    assert (
        client.post("/api/v1/admin/settings/ip2region/update").status_code
        == 202
    )
    body = _wait_ip2region_status(client, lambda s: s["state"] == "error")
    assert "未列入信任清单" in body["message"]


def test_ip2region_manual_update_requires_admin(
    client, captured_email, tmp_path, monkeypatch
) -> None:
    _isolate_ip2region(tmp_path, monkeypatch)
    assert client.post("/api/v1/admin/settings/ip2region/update").status_code == 401
    assert (
        client.get(
            "/api/v1/admin/settings/ip2region/update/status"
        ).status_code
        == 401
    )
    register_and_login(client, captured_email)
    assert (
        client.post("/api/v1/admin/settings/ip2region/update").status_code == 403
    )
    assert (
        client.get(
            "/api/v1/admin/settings/ip2region/update/status"
        ).status_code
        == 403
    )
