from datetime import datetime, timezone
import os
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.services import ip2region_update as update
from app.services.ip2region_update import (
    AUTO_UPDATE_ENABLED_KEY,
    UPDATE_INTERVAL_HOURS_KEY,
)
from app.services.site_settings import set_site_setting_bool, set_site_setting_int


def _header(ip_version: int, created_at: int):
    class FakeHeader:
        ipVersion = ip_version
        createdAt = created_at

    return FakeHeader()


def test_read_write_meta_roundtrip(tmp_path):
    payload = {
        "version": "v3.17.0",
        "data_updated_at": "2026-07-09T00:00:00+00:00",
    }
    update.write_meta(tmp_path, payload)
    assert update.read_meta(tmp_path) == payload


def test_install_validates_and_swaps(tmp_path, monkeypatch):
    from ip2region import util

    v4_src = tmp_path / "new_v4.xdb"
    v6_src = tmp_path / "new_v6.xdb"
    v4_src.write_bytes(b"v4")
    v6_src.write_bytes(b"v6")
    monkeypatch.setattr(util, "verify_from_file", lambda path: None)
    monkeypatch.setattr(
        util,
        "load_header_from_file",
        lambda path: (
            _header(4, 1783612371)
            if str(path).endswith("new_v4.xdb")
            else _header(6, 1783612278)
        ),
    )
    # 本用例聚焦“结构校验 + 原子替换”逻辑，SHA256 信任清单单独测试。
    monkeypatch.setattr(update, "_verify_pinned_hashes", lambda *args: None)
    reloaded = []
    monkeypatch.setattr(
        update, "reload_geoip_resolver", lambda: reloaded.append(1)
    )

    result = update.install(tmp_path / "data", v4_src, v6_src, "v3.17.0")

    assert (tmp_path / "data" / "ip2region_v4.xdb").read_bytes() == b"v4"
    assert (tmp_path / "data" / "ip2region_v6.xdb").read_bytes() == b"v6"
    assert result["version"] == "v3.17.0"
    assert result["data_updated_at"] == "2026-07-09T15:52:51+00:00"
    assert reloaded == [1]


def test_install_rejects_mismatched_header(tmp_path, monkeypatch):
    from ip2region import util

    monkeypatch.setattr(util, "verify_from_file", lambda path: None)
    monkeypatch.setattr(util, "load_header_from_file", lambda path: _header(6, 1))
    # 本用例聚焦文件头 IP 版本校验，SHA256 信任清单单独测试。
    monkeypatch.setattr(update, "_verify_pinned_hashes", lambda *args: None)
    v4_src = tmp_path / "bad_v4.xdb"
    v4_src.write_bytes(b"bad")
    with pytest.raises(ValueError):
        update.install(tmp_path / "data", v4_src, v4_src, "v3.17.0")


def test_install_rejects_version_not_in_trust_list(tmp_path, monkeypatch):
    """运行期仅允许安装信任清单内的版本，未知版本必须拒绝。"""
    from ip2region import util

    monkeypatch.setattr(util, "verify_from_file", lambda path: None)
    monkeypatch.setattr(util, "load_header_from_file", lambda path: _header(4, 1))
    v4_src = tmp_path / "v4.xdb"
    v6_src = tmp_path / "v6.xdb"
    v4_src.write_bytes(b"v4")
    v6_src.write_bytes(b"v6")

    with pytest.raises(RuntimeError, match="信任清单"):
        update.install(tmp_path / "data", v4_src, v6_src, "v9.9.9")


def test_install_rejects_sha256_mismatch(tmp_path, monkeypatch):
    """信任清单内版本的下载文件哈希不符时必须拒绝，保留旧库。"""
    from ip2region import util

    monkeypatch.setattr(util, "verify_from_file", lambda path: None)
    monkeypatch.setattr(
        util,
        "load_header_from_file",
        lambda path: _header(4, 1) if "v4" in str(path) else _header(6, 1),
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ip2region_v4.xdb").write_bytes(b"old-v4")
    (data_dir / "ip2region_v6.xdb").write_bytes(b"old-v6")
    v4_src = tmp_path / "v4.xdb"
    v6_src = tmp_path / "v6.xdb"
    v4_src.write_bytes(b"tampered-v4")
    v6_src.write_bytes(b"tampered-v6")

    with pytest.raises(ValueError, match="SHA256"):
        update.install(data_dir, v4_src, v6_src, "v3.17.0")

    # 校验失败不得破坏旧库
    assert (data_dir / "ip2region_v4.xdb").read_bytes() == b"old-v4"
    assert (data_dir / "ip2region_v6.xdb").read_bytes() == b"old-v6"


def test_install_rolls_back_on_partial_replace(tmp_path, monkeypatch):
    """新库替换中途失败时必须回滚，不能留下 v4/v6 版本不一致。"""
    from ip2region import util

    monkeypatch.setattr(util, "verify_from_file", lambda path: None)
    monkeypatch.setattr(
        util,
        "load_header_from_file",
        lambda path: _header(4, 1) if "v4" in str(path) else _header(6, 1),
    )
    monkeypatch.setattr(update, "_verify_pinned_hashes", lambda *args: None)

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ip2region_v4.xdb").write_bytes(b"old-v4")
    (data_dir / "ip2region_v6.xdb").write_bytes(b"old-v6")
    v4_src = tmp_path / "v4.xdb"
    v6_src = tmp_path / "v6.xdb"
    v4_src.write_bytes(b"new-v4")
    v6_src.write_bytes(b"new-v6")

    real_replace = os.replace
    calls = []

    def failing_replace(src, dst):
        calls.append((src, dst))
        if len(calls) == 4:
            raise OSError("simulated ENOSPC")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError):
        update.install(data_dir, v4_src, v6_src, "v3.17.0")

    assert (data_dir / "ip2region_v4.xdb").read_bytes() == b"old-v4"
    assert (data_dir / "ip2region_v6.xdb").read_bytes() == b"old-v6"


def test_update_rejects_concurrent_process(db_session, tmp_path, monkeypatch):
    """同一数据目录已有更新任务时（跨进程锁），必须立即拒绝。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )
    with update._file_update_lock(data_dir):
        fetched = []
        monkeypatch.setattr(
            update,
            "fetch_latest_version",
            lambda: fetched.append(1) or "v3.17.0",
        )
        with pytest.raises(RuntimeError, match="已有更新任务进行中"):
            update.update_ip2region(db_session)
        assert fetched == []


def test_update_skips_download_when_current(db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ip2region_v4.xdb").write_bytes(b"v4")
    (data_dir / "ip2region_v6.xdb").write_bytes(b"v6")
    update.write_meta(
        data_dir,
        {
            "version": "v3.17.0",
            "data_updated_at": "2026-07-09T15:52:51+00:00",
        },
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )
    fetched = []
    monkeypatch.setattr(
        update,
        "fetch_latest_version",
        lambda: fetched.append("v3.17.0") or "v3.17.0",
    )
    result = update.update_ip2region(db_session)
    assert result == {
        "version": "v3.17.0",
        "data_updated_at": "2026-07-09T15:52:51+00:00",
        "changed": False,
    }
    assert fetched == ["v3.17.0"]


def test_status_reflects_settings(db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ip2region_v4.xdb").write_bytes(b"v4")
    (data_dir / "ip2region_v6.xdb").write_bytes(b"v6")
    update.write_meta(
        data_dir,
        {
            "version": "v3.17.0",
            "data_updated_at": "2026-07-09T00:00:00+00:00",
        },
    )
    set_site_setting_bool(db_session, AUTO_UPDATE_ENABLED_KEY, True)
    set_site_setting_int(db_session, UPDATE_INTERVAL_HOURS_KEY, 48)
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )

    status = update.ip2region_status(db_session)

    assert status["version"] == "v3.17.0"
    assert status["v4_ready"] is True and status["v6_ready"] is True
    assert status["auto_update_enabled"] is True
    assert status["update_interval_hours"] == 48


def test_maybe_auto_update_respects_interval(db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    update.write_meta(
        data_dir,
        {
            "version": "v3.17.0",
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_auto_update_enabled", True
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_update_interval_hours", 24
    )
    calls = []
    monkeypatch.setattr(update, "update_ip2region", lambda db: calls.append(1))
    update.maybe_auto_update(db_session)
    assert calls == []


def test_maybe_auto_update_clamps_nonpositive_interval(
    db_session, tmp_path, monkeypatch
) -> None:
    """站点设置被改坏为 0/负值时不得退化为每小时更新。"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    update.write_meta(
        data_dir,
        {
            "version": "v3.17.0",
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_auto_update_enabled", True
    )
    monkeypatch.setattr(
        update.get_settings(), "ip2region_update_interval_hours", 0
    )
    set_site_setting_int(db_session, UPDATE_INTERVAL_HOURS_KEY, 0)
    calls = []
    monkeypatch.setattr(update, "update_ip2region", lambda db: calls.append(1))

    update.maybe_auto_update(db_session)

    assert calls == []


def test_update_logs_audit_when_changed(db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(
        update.get_settings(), "ip2region_data_dir", str(data_dir)
    )
    monkeypatch.setattr(update, "fetch_latest_version", lambda: "v9.9.9")
    monkeypatch.setattr(
        update,
        "_download_to",
        lambda url, destination, timeout: destination.write_bytes(b"x"),
    )
    monkeypatch.setattr(
        update,
        "install",
        lambda d, v4, v6, version: {
            "version": version,
            "data_updated_at": "2026-08-14T00:00:00+00:00",
        },
    )
    actor = SimpleNamespace(id="admin-1")
    request = SimpleNamespace(
        client=SimpleNamespace(host="10.0.0.9"), headers={}
    )

    result = update.update_ip2region(db_session, actor=actor, request=request)

    assert result["changed"] is True
    logs = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "admin_update_ip2region")
    ).all()
    assert len(logs) == 1
    assert logs[0].detail["version"] == "v9.9.9"
    assert logs[0].ip == "10.0.0.9"
