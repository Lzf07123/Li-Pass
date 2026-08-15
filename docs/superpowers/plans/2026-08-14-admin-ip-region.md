# 管理后台 IP 归属地展示、统计与库更新 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会话/审计展示 IP 归属地，数据统计新增登录来源地域分布，站点设置新增 ip2region 离线库的手动与定期自动更新。

**Architecture:** 后端锁定官方 ip2region v3.17.0 Python 绑定入 `backend/ip2region/`，新增懒加载线程安全解析服务与更新服务（下载→校验→原子替换→meta.json→热重载）；会话/审计序列化追加 `ip_location`，统计聚合追加 `regions`，站点设置扩展状态与更新端点，`main.py` lifespan 增加自动更新后台任务。前端在会话/审计/统计/设置四个面板呈现。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + ip2region xdb（后端，无新增 pip 依赖）；React 19 + TypeScript + Tailwind CSS 4（前端，无新增 npm 依赖）。

## Global Constraints

- xdb 字段：`国家|省份|城市|ISP|iso-alpha2`，空值 `0`/空串；中国显示「省份 城市」，海外显示国家，不显示 ISP。
- IP 分类优先：`private/loopback/link_local/unspecified` → `内网地址`；`multicast/reserved` → `保留地址`；IPv4-mapped IPv6 先归一化为 IPv4。
- 解析完全离线且永不抛异常：无效 IP、xdb 缺失 → `None`（前端 `—`）。
- `regions`：窗口内成功登录（`action IN ('login','2fa_login')`）按 `GROUP BY ip` 去重后解析，Top 10 降序 + 「其它」；xdb 未安装返回 `[]`。
- 更新：结构校验 `verify_from_file` + 文件头 `ipVersion` 校验（v4=4、v6=6）+ 原子替换 + meta.json；任一失败保留旧库。
- 手动更新限流默认 6 次/小时（按管理员）；更新成功记审计 `admin_update_ip2region`。
- 自动更新默认关闭，间隔默认 24h（1–8760）；后台任务每小时醒来检查站点设置。
- 时区 Asia/Shanghai；颜色只用 CSS 变量令牌；不播放动画；只读接口不记审计。

---

## 文件结构

- Create: `backend/ip2region/__init__.py`、`backend/ip2region/{__init__,searcher,util}.py`、`backend/ip2region/LICENSE`（v3.17.0 官方源码逐字复制）
- Create: `backend/app/services/geoip.py`、`backend/app/services/ip2region_update.py`
- Create: `backend/scripts/download_ip2region.py`
- Modify: `backend/app/core/config.py`、`backend/app/services/site_settings.py`、`backend/app/services/admin_stats.py`、`backend/app/api/routes/admin_sessions.py`、`backend/app/api/routes/admin_users.py`、`backend/app/api/routes/admin_settings.py`、`backend/app/main.py`、`backend/app/schemas/auth.py`
- Test: `backend/tests/test_geoip.py`、`backend/tests/test_ip2region_update.py`；扩展 `test_admin_stats.py`、`test_admin_sessions.py`、`test_admin_settings.py`、`test_audit_filters.py`
- Modify: `frontend/src/api/types.ts`、`frontend/src/api/client.ts`、`frontend/src/pages/AdminSessionsPanel.tsx`、`frontend/src/pages/AdminAuditPanel.tsx`、`frontend/src/pages/AdminStatsPanel.tsx`、`frontend/src/pages/AdminSettingsPanel.tsx`
- Test: `frontend/src/__tests__/AdminSettingsPanel.test.tsx`；扩展 `AdminSessionsPanel.test.tsx`、`AdminAuditPanel.test.tsx`、`AdminStatsPanel.test.tsx`
- Modify: `backend/Dockerfile`、`docker-compose.yaml`、`.env.example`、`.gitignore`、`docs/deployment.md`、`CHANGELOG.md`

---

## Task 1: 锁定 ip2region 绑定与配置项

**Files:**
- Create: `backend/ip2region/__init__.py`、`backend/ip2region/__init__.py`、`backend/ip2region/searcher.py`、`backend/ip2region/util.py`、`backend/ip2region/LICENSE`
- Modify: `backend/app/core/config.py`、`.gitignore`

**Interfaces:**
- Produces: 顶层包 `ip2region`（`searcher.new_with_buffer(version, c_buffer)`、`util.IPv4/IPv6/XdbIPv4Id/XdbIPv6Id/verify_from_file/load_header_from_file/load_content_from_file`）。
- Produces 配置：`ip2region_data_dir`、`ip2region_releases_api_url`、`ip2region_download_base_url`、`ip2region_http_timeout_seconds`、`ip2region_auto_update_enabled`、`ip2region_update_interval_hours`、`ip2region_update_rate_limit`、`ip2region_update_rate_window_seconds`。

- [ ] **Step 1:** 用 `apply_patch` 从 `/tmp/ip2region-pkg/` 的内容逐字创建 `backend/ip2region/{__init__,searcher,util}.py` 与 `LICENSE`（保留 Apache-2.0 头），并新建空 `backend/ip2region/__init__.py`。校验：`cmp` 与 `/tmp/ip2region-pkg/*` 一致。
- [ ] **Step 2:** `.gitignore` 末尾追加 `# ip2region 离线数据（构建/脚本下载，不入库）` 与 `backend/data/`。
- [ ] **Step 3:** `config.py` 增加字段（置于 `db_max_overflow` 之后）：

```python
    # ip2region 离线 IP 库：数据目录、更新源与调度（详见 ip2region_update 服务）
    ip2region_data_dir: str = "data/ip2region"
    ip2region_releases_api_url: str = (
        "https://api.github.com/repos/lionsoul2014/ip2region/releases/latest"
    )
    ip2region_download_base_url: str = (
        "https://raw.githubusercontent.com/lionsoul2014/ip2region"
    )
    ip2region_http_timeout_seconds: float = 30.0
    ip2region_auto_update_enabled: bool = False
    ip2region_update_interval_hours: int = 24
    ip2region_update_rate_limit: int = 6
    ip2region_update_rate_window_seconds: int = 3600
```

- [ ] **Step 4:** `_validate_production` 的通用校验段追加：`ip2region_http_timeout_seconds >= 5`、`1 <= ip2region_update_interval_hours <= 8760`、`ip2region_update_rate_limit >= 1`、`ip2region_update_rate_window_seconds >= 1`；生产段追加 `ip2region_data_dir` 必须以 `/` 开头（与 keys 一致）。
- [ ] **Step 5:** Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_settings.py tests/test_admin_system.py -q` → PASS（配置未被破坏）。
- [ ] **Step 6:** 无独立提交（随功能整体评审）。

---

## Task 2: 归属地解析服务 geoip.py

**Files:**
- Create: `backend/app/services/geoip.py`
- Test: `backend/tests/test_geoip.py`

**Interfaces:**
- Consumes: `ip2region`（Task 1）、`get_settings()`
- Produces:
  - `GeoIpResult(country: str|None, province: str|None, city: str|None, isp: str|None, display: str)`（frozen dataclass）
  - `format_region(region: str) -> GeoIpResult`
  - `normalize_ip(ip: str) -> tuple[str|None, str|None]`（(规范化 IP, 分类标签)；无效 IP → (None, None)）
  - `describe_ip(ip: str|None) -> str|None`
  - `get_geoip_resolver() -> GeoIpResolver`、`reload_geoip_resolver()`、`resolver_ready() -> bool`
  - `GeoIpResolver(v4_path: Path, v6_path: Path)` 的 `.resolve(ip) -> GeoIpResult|None`、`.is_ready() -> bool`

- [ ] **Step 1: 写失败测试** `tests/test_geoip.py`

```python
from app.services.geoip import format_region, normalize_ip


def test_format_region_china_joins_province_and_city():
    result = format_region("中国|广东省|深圳市|电信|CN")
    assert result.country == "中国"
    assert result.display == "广东省 深圳市"
    assert result.isp == "电信"


def test_format_region_overseas_uses_country():
    result = format_region("United States|California|San Jose|xTom|US")
    assert result.display == "United States"


def test_format_region_empty_placeholders():
    result = format_region("中国|0|0|0|CN")
    assert result.display == "中国"
    assert result.city is None


def test_format_region_unknown():
    result = format_region("")
    assert result.display == "未知"


def test_normalize_ip_classification():
    assert normalize_ip("192.168.1.1") == ("192.168.1.1", "内网地址")
    assert normalize_ip("127.0.0.1") == ("127.0.0.1", "内网地址")
    assert normalize_ip("fe80::1") == ("fe80::1", "内网地址")
    assert normalize_ip("224.0.0.1") == ("224.0.0.1", "保留地址")
    assert normalize_ip("192.0.2.1") == ("192.0.2.1", "保留地址")
    assert normalize_ip("::ffff:192.168.1.1") == ("192.168.1.1", "内网地址")
    assert normalize_ip("1.2.3.4") == ("1.2.3.4", None)
    assert normalize_ip("not-an-ip") == (None, None)


def test_describe_ip_returns_none_without_resolver(monkeypatch):
    from app.services import geoip

    class FakeResolver:
        def resolve(self, ip):
            return None

    monkeypatch.setattr(geoip, "get_geoip_resolver", lambda: FakeResolver())
    assert geoip.describe_ip("8.8.8.8") is None
    assert geoip.describe_ip("192.168.0.1") == "内网地址"
```

- [ ] **Step 2:** Run: `cd backend && .venv/bin/python -m pytest tests/test_geoip.py -q` → FAIL（模块不存在）
- [ ] **Step 3:** 实现 `app/services/geoip.py`：

```python
"""离线 IP 归属地解析：ip2region xdb 懒加载 + 进程内缓存。"""

import ipaddress
import logging
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from ip2region import searcher as ip2region_searcher
from ip2region import util as ip2region_util

logger = logging.getLogger(__name__)

_UNSET_FIELDS = {"", "0"}
_INTERNAL_LABEL = "内网地址"
_RESERVED_LABEL = "保留地址"
_UNKNOWN_LABEL = "未知"


@dataclass(frozen=True)
class GeoIpResult:
    country: str | None
    province: str | None
    city: str | None
    isp: str | None
    display: str


def _split_region(region: str) -> list[str | None]:
    parts = region.split("|")
    while len(parts) < 5:
        parts.append("")
    return [
        None if part.strip() in _UNSET_FIELDS else part.strip()
        for part in parts[:5]
    ]


def format_region(region: str) -> GeoIpResult:
    country, province, city, isp, _code = _split_region(region)
    if country is None:
        return GeoIpResult(None, province, city, isp, _UNKNOWN_LABEL)
    if country in ("Reserved", "保留地址"):
        return GeoIpResult(country, province, city, isp, _RESERVED_LABEL)
    if country == "中国":
        tail = " ".join(part for part in (province, city) if part)
        return GeoIpResult(country, province, city, isp, tail or country)
    return GeoIpResult(country, province, city, isp, country)


def normalize_ip(ip: str) -> tuple[str | None, str | None]:
    """返回 (规范化 IP, 分类标签)；无效 IP 返回 (None, None)。"""
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None, None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    normalized = str(address)
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    ):
        return normalized, _INTERNAL_LABEL
    if address.is_multicast or address.is_reserved:
        return normalized, _RESERVED_LABEL
    return normalized, None


class GeoIpResolver:
    """进程级单例：content-buffer 模式线程安全；文件被替换后自动重载。"""

    def __init__(self, v4_path: Path, v6_path: Path) -> None:
        self._v4_path = str(v4_path)
        self._v6_path = str(v6_path)
        self._lock = threading.Lock()
        self._loaded: tuple | None = None  # (sig_v4, sig_v6, v4, v6)

    @staticmethod
    def _signature(path: str) -> tuple[int, int] | None:
        try:
            stat = os.stat(path)
        except OSError:
            return None
        return stat.st_mtime_ns, stat.st_size

    @staticmethod
    def _load_one(version, path: str):
        content = ip2region_util.load_content_from_file(path)
        return ip2region_searcher.new_with_buffer(version, content)

    def _ensure(self) -> None:
        signature = (
            self._signature(self._v4_path),
            self._signature(self._v6_path),
        )
        with self._lock:
            if self._loaded is not None and self._loaded[:2] == signature:
                return
            try:
                v4 = self._load_one(ip2region_util.IPv4, self._v4_path)
                v6 = self._load_one(ip2region_util.IPv6, self._v6_path)
            except (OSError, ValueError) as exc:
                if self._loaded is None:
                    self._loaded = (None, None, None, None)
                logger.warning("ip2region 数据加载失败：%s", exc)
                return
            self._loaded = (*signature, v4, v6)

    def is_ready(self) -> bool:
        self._ensure()
        return bool(self._loaded and self._loaded[2] is not None)

    def resolve(self, ip: str) -> GeoIpResult | None:
        normalized, label = normalize_ip(ip)
        if label == _INTERNAL_LABEL:
            return GeoIpResult(None, None, None, None, _INTERNAL_LABEL)
        if label == _RESERVED_LABEL:
            return GeoIpResult(None, None, None, None, _RESERVED_LABEL)
        if normalized is None:
            return None
        self._ensure()
        if not self._loaded or self._loaded[2] is None:
            return None
        searcher = self._loaded[3] if ":" in normalized else self._loaded[2]
        try:
            region = searcher.search(normalized)
        except ValueError:
            return None
        if not region:
            return None
        return format_region(region)


_resolver: GeoIpResolver | None = None
_resolver_lock = threading.Lock()


def get_geoip_resolver() -> GeoIpResolver:
    global _resolver
    if _resolver is None:
        with _resolver_lock:
            if _resolver is None:
                settings = get_settings()
                _resolver = GeoIpResolver(
                    Path(settings.ip2region_data_dir) / "ip2region_v4.xdb",
                    Path(settings.ip2region_data_dir) / "ip2region_v6.xdb",
                )
    return _resolver


def reload_geoip_resolver() -> None:
    get_geoip_resolver()._loaded = None


def resolver_ready() -> bool:
    return get_geoip_resolver().is_ready()


def describe_ip(ip: str | None) -> str | None:
    if not ip:
        return None
    normalized, label = normalize_ip(ip)
    if label:
        return label
    if normalized is None:
        return None
    result = get_geoip_resolver().resolve(normalized)
    return result.display if result else None
```

- [ ] **Step 4:** Run 同一命令 → PASS；随后 `cd backend && .venv/bin/python -c "from app.services.geoip import *; print(describe_ip('223.104.60.77'))"`（本地放入 `backend/data/ip2region/` 后冒烟，未放时允许返回 None）。
- [ ] **Step 5:** 无独立提交。

---

## Task 3: 站点设置整数助手

**Files:**
- Modify: `backend/app/services/site_settings.py`
- Test: `backend/tests/test_site_settings.py`

**Interfaces:**
- Produces: `get_site_setting_int(db, key: str, default: int) -> int`、`set_site_setting_int(db, key: str, value: int) -> None`

- [ ] **Step 1: 写失败测试**：`get_site_setting_int` 无行时返回 default；写入后读回；存量脏字符串返回 default；`set_site_setting_int` 覆盖更新。
- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** 实现：

```python
def get_site_setting_int(db: Session, key: str, default: int) -> int:
    row = db.get(SiteSetting, key)
    if row is None:
        return default
    try:
        return int(row.value.strip())
    except ValueError:
        return default


def set_site_setting_int(db: Session, key: str, value: int) -> None:
    text = str(value)
    row = db.get(SiteSetting, key)
    if row is None:
        db.add(SiteSetting(key=key, value=text))
    else:
        row.value = text
    db.commit()
```

- [ ] **Step 4:** Run → PASS

---

## Task 4: 会话/审计追加 ip_location

**Files:**
- Modify: `backend/app/api/routes/admin_sessions.py`、`backend/app/api/routes/admin_users.py`、`backend/app/schemas/auth.py`
- Test: `backend/tests/test_admin_sessions.py`、`backend/tests/test_audit_filters.py`

**Interfaces:**
- Consumes: `describe_ip`（Task 2）
- Produces: `AdminSessionOut.ip_location: str | None = None`；会话/审计响应的每个元素含 `ip_location`。

- [ ] **Step 1: 写失败测试**：`test_admin_sessions.py` 中 monkeypatch `app.services.geoip.describe_ip` 固定返回 `"广东省 深圳市"`，断言列表项 `ip_location == "广东省 深圳市"`；`test_audit_filters.py` 断言审计项含 `ip_location` 键。
- [ ] **Step 2:** Run → FAIL（键缺失）
- [ ] **Step 3:** `admin_sessions.py`：import `from app.services.geoip import describe_ip`；`_serialize_session` 的 `"user_agent"` 后加 `"ip_location": describe_ip(session.ip)`。`schemas/auth.py` 的 `AdminSessionOut` 加 `ip_location: str | None = None`。`admin_users.py` 的 `list_audit_logs` 返回 dict 加 `"ip_location": describe_ip(log.ip)`（import 同步追加）。
- [ ] **Step 4:** Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_sessions.py tests/test_audit_filters.py tests/test_admin_users_management.py -q` → PASS

---

## Task 5: 统计接口追加 regions

**Files:**
- Modify: `backend/app/services/admin_stats.py`
- Test: `backend/tests/test_admin_stats.py`

**Interfaces:**
- Consumes: `describe_ip`、`resolver_ready`（Task 2）
- Produces: `collect_admin_stats(...)["regions"]`：`list[{"region": str, "count": int}]`，Top 10 降序 + 「其它」。

- [ ] **Step 1: 写失败测试**：

```python
def test_admin_stats_regions_top_and_other(client, db_session, monkeypatch) -> None:
    from app.services import geoip

    fake = {"1.1.1.1": "广东省 深圳市", "8.8.8.8": "United States"}
    monkeypatch.setattr(geoip, "resolver_ready", lambda: True)
    monkeypatch.setattr(
        geoip, "describe_ip", lambda ip: fake.get(ip, "未知")
    )
    now = datetime.now(timezone.utc)
    u1 = make_user(db_session, "u1@example.com")
    db_session.add_all(
        [
            AuditLog(actor_type="user", actor_id=str(u1.id),
                     action="login", category="auth", ip="1.1.1.1",
                     created_at=now - timedelta(hours=1)),
            AuditLog(actor_type="user", actor_id=str(u1.id),
                     action="login", category="auth", ip="1.1.1.1",
                     created_at=now - timedelta(hours=2)),
            AuditLog(actor_type="user", actor_id=str(u1.id),
                     action="2fa_login", category="auth", ip="8.8.8.8",
                     created_at=now - timedelta(hours=3)),
        ]
    )
    db_session.commit()
    login_admin(client, db_session)
    regions = client.get("/api/v1/admin/stats?days=7").json()["regions"]
    assert regions == [
        {"region": "广东省 深圳市", "count": 2},
        {"region": "United States", "count": 1},
    ]


def test_admin_stats_regions_empty_without_db(client, db_session, monkeypatch) -> None:
    from app.services import geoip

    monkeypatch.setattr(geoip, "resolver_ready", lambda: False)
    login_admin(client, db_session)
    assert client.get("/api/v1/admin/stats?days=7").json()["regions"] == []
```

- [ ] **Step 2:** Run → FAIL（`KeyError: 'regions'`）
- [ ] **Step 3:** `admin_stats.py` import `from app.services import geoip`，新增：

```python
REGION_TOP_N = 10


def _regions(db: Session, days: int, now: datetime) -> list[dict]:
    if not geoip.resolver_ready():
        return []
    start = now - timedelta(days=days)
    rows = db.execute(
        select(AuditLog.ip, func.count())
        .where(
            AuditLog.action.in_(LOGIN_ACTIONS),
            AuditLog.created_at >= start,
            AuditLog.created_at < now,
            AuditLog.ip.is_not(None),
        )
        .group_by(AuditLog.ip)
    ).all()
    counts: dict[str, int] = {}
    for ip, count in rows:
        if not ip:
            continue
        key = geoip.describe_ip(ip) or "未知"
        counts[key] = counts.get(key, 0) + int(count)
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    result = [
        {"region": name, "count": count} for name, count in ordered[:REGION_TOP_N]
    ]
    rest = sum(count for _, count in ordered[REGION_TOP_N:])
    if rest:
        result.append({"region": "其它", "count": rest})
    return result
```

并在 `collect_admin_stats` 的返回 dict 加 `"regions": _regions(db, days, now)`。

- [ ] **Step 4:** Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_stats.py -q` → PASS

---

## Task 6: 更新服务与下载脚本

**Files:**
- Create: `backend/app/services/ip2region_update.py`、`backend/scripts/download_ip2region.py`
- Test: `backend/tests/test_ip2region_update.py`

**Interfaces:**
- Consumes: `ip2region.util`、`get_site_setting_bool/int`、`set_site_setting_*`（Task 3）、`reload_geoip_resolver`（Task 2）
- Produces:
  - `fetch_latest_version() -> str`
  - `read_meta(data_dir: Path) -> dict`、`write_meta(data_dir: Path, payload: dict) -> None`
  - `data_timestamp(data_dir: Path) -> str | None`
  - `install(data_dir: Path, v4_src: Path, v6_src: Path, version: str) -> dict`（返回 `{"version","data_updated_at"}`）
  - `update_ip2region(db, actor=None, request=None) -> dict`（返回 `{"version","data_updated_at","changed"}`）
  - `ip2region_status(db) -> dict`（键：`version/data_updated_at/v4_ready/v6_ready/auto_update_enabled/update_interval_hours`）
  - `maybe_auto_update(db) -> None`
  - 常量 `AUTO_UPDATE_ENABLED_KEY = "ip2region_auto_update_enabled"`、`UPDATE_INTERVAL_HOURS_KEY = "ip2region_update_interval_hours"`

- [ ] **Step 1: 写失败测试**（monkeypatch 网络与 ip2region 结构校验，覆盖编排而非真实下载）：

```python
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services import ip2region_update as update
from app.services.ip2region_update import (
    AUTO_UPDATE_ENABLED_KEY, UPDATE_INTERVAL_HOURS_KEY,
)


def _header(ip_version: int, created_at: int):
    class FakeHeader:
        ipVersion = ip_version
        createdAt = created_at
    return FakeHeader()


def test_read_write_meta_roundtrip(tmp_path):
    payload = {"version": "v3.17.0", "data_updated_at": "2026-07-09T00:00:00+00:00"}
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
        util, "load_header_from_file",
        lambda path: _header(4, 1783612371) if str(path).endswith("v4") else _header(6, 1783612278),
    )
    reloaded = []
    monkeypatch.setattr(update, "reload_geoip_resolver", lambda: reloaded.append(1))

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
    v4_src = tmp_path / "bad_v4.xdb"
    v4_src.write_bytes(b"bad")
    import pytest
    with pytest.raises(ValueError):
        update.install(tmp_path / "data", v4_src, v4_src, "v9")


def test_update_skips_download_when_current(client, db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    update.write_meta(data_dir, {"version": "v3.17.0"})
    monkeypatch.setattr(update.get_settings(), "ip2region_data_dir", str(data_dir))
    fetched = []
    monkeypatch.setattr(update, "fetch_latest_version", lambda: fetched.append("v3.17.0") or "v3.17.0")
    result = update.update_ip2region(db_session)
    assert result == {"version": "v3.17.0", "data_updated_at": None, "changed": False}
    assert fetched == ["v3.17.0"]


def test_status_reflects_settings(client, db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "ip2region_v4.xdb").write_bytes(b"v4")
    (data_dir / "ip2region_v6.xdb").write_bytes(b"v6")
    update.write_meta(data_dir, {"version": "v3.17.0", "data_updated_at": "2026-07-09T00:00:00+00:00"})
    from app.services.site_settings import set_site_setting_bool, set_site_setting_int
    set_site_setting_bool(db_session, AUTO_UPDATE_ENABLED_KEY, True)
    set_site_setting_int(db_session, UPDATE_INTERVAL_HOURS_KEY, 48)
    monkeypatch.setattr(update.get_settings(), "ip2region_data_dir", str(data_dir))

    status = update.ip2region_status(db_session)

    assert status["version"] == "v3.17.0"
    assert status["v4_ready"] is True and status["v6_ready"] is True
    assert status["auto_update_enabled"] is True
    assert status["update_interval_hours"] == 48


def test_maybe_auto_update_respects_interval(client, db_session, tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    update.write_meta(data_dir, {
        "version": "v3.17.0",
        "last_check_at": datetime.now(timezone.utc).isoformat(),
    })
    monkeypatch.setattr(update.get_settings(), "ip2region_data_dir", str(data_dir))
    monkeypatch.setattr(update.get_settings(), "ip2region_auto_update_enabled", True)
    monkeypatch.setattr(update.get_settings(), "ip2region_update_interval_hours", 24)
    calls = []
    monkeypatch.setattr(update, "update_ip2region", lambda db: calls.append(1))
    update.maybe_auto_update(db_session)
    assert calls == []
```

> 注意：测试经 `conftest` 的 `client` 装配 `get_settings()` 已带默认值；`install` 的 `createdAt=1783612371` 对应 `2026-07-09T15:52:51+00:00`（以 `datetime.fromtimestamp(..., timezone.utc)` 为准）。

- [ ] **Step 2:** Run → FAIL（模块不存在）
- [ ] **Step 3:** 实现 `ip2region_update.py`：

```python
"""ip2region 离线库的状态、下载、校验、原子替换与自动更新调度。"""

import hashlib
import json
import logging
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.audit import log_audit
from app.services.geoip import reload_geoip_resolver
from app.services.site_settings import (
    get_site_setting_bool,
    get_site_setting_int,
)
from ip2region import util as ip2region_util

logger = logging.getLogger(__name__)

V4_FILENAME = "ip2region_v4.xdb"
V6_FILENAME = "ip2region_v6.xdb"
META_FILENAME = "meta.json"
AUTO_UPDATE_ENABLED_KEY = "ip2region_auto_update_enabled"
UPDATE_INTERVAL_HOURS_KEY = "ip2region_update_interval_hours"

_update_lock = threading.Lock()


def _http_get_json(url: str, timeout: float) -> dict:
    request = Request(url, headers={"User-Agent": "Li&Pass/1.0"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError("版本接口返回格式异常")
    return payload


def fetch_latest_version() -> str:
    settings = get_settings()
    payload = _http_get_json(
        settings.ip2region_releases_api_url,
        settings.ip2region_http_timeout_seconds,
    )
    tag = payload.get("tag_name")
    if not tag:
        raise RuntimeError("无法从版本接口解析最新版本号")
    return str(tag)


def _download_to(url: str, destination: Path, timeout: float) -> None:
    request = Request(url, headers={"User-Agent": "Li&Pass/1.0"})
    with urlopen(request, timeout=timeout) as response, open(destination, "wb") as out:
        shutil.copyfileobj(response, out)


def read_meta(data_dir: Path) -> dict:
    path = data_dir / META_FILENAME
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def write_meta(data_dir: Path, payload: dict) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / META_FILENAME
    temp = path.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    os.replace(temp, path)


def data_timestamp(data_dir: Path) -> str | None:
    path = data_dir / V4_FILENAME
    try:
        header = ip2region_util.load_header_from_file(str(path))
    except (OSError, ValueError):
        return None
    return datetime.fromtimestamp(header.createdAt, timezone.utc).isoformat()


def install(data_dir: Path, v4_src: Path, v6_src: Path, version: str) -> dict:
    for source in (v4_src, v6_src):
        ip2region_util.verify_from_file(str(source))
    v4_header = ip2region_util.load_header_from_file(str(v4_src))
    v6_header = ip2region_util.load_header_from_file(str(v6_src))
    if v4_header.ipVersion != ip2region_util.XdbIPv4Id:
        raise ValueError("v4 文件头 IP 版本不匹配")
    if v6_header.ipVersion != ip2region_util.XdbIPv6Id:
        raise ValueError("v6 文件头 IP 版本不匹配")
    data_dir.mkdir(parents=True, exist_ok=True)
    os.replace(v4_src, data_dir / V4_FILENAME)
    os.replace(v6_src, data_dir / V6_FILENAME)
    timestamp = datetime.fromtimestamp(
        v4_header.createdAt, timezone.utc
    ).isoformat()
    meta = read_meta(data_dir)
    meta.update({
        "version": version,
        "data_updated_at": timestamp,
        "v4_sha256": hashlib.sha256((data_dir / V4_FILENAME).read_bytes()).hexdigest(),
        "v6_sha256": hashlib.sha256((data_dir / V6_FILENAME).read_bytes()).hexdigest(),
        "last_check_at": datetime.now(timezone.utc).isoformat(),
    })
    write_meta(data_dir, meta)
    reload_geoip_resolver()
    return {"version": version, "data_updated_at": timestamp}


def update_ip2region(db: Session, actor=None, request=None) -> dict:
    settings = get_settings()
    data_dir = Path(settings.ip2region_data_dir)
    if not _update_lock.acquire(blocking=False):
        raise RuntimeError("已有更新任务进行中")
    try:
        latest = fetch_latest_version()
        meta = read_meta(data_dir)
        both_ready = (data_dir / V4_FILENAME).is_file() and (
            data_dir / V6_FILENAME
        ).is_file()
        if meta.get("version") == latest and both_ready:
            meta["last_check_at"] = datetime.now(timezone.utc).isoformat()
            write_meta(data_dir, meta)
            return {
                "version": latest,
                "data_updated_at": meta.get("data_updated_at")
                or data_timestamp(data_dir),
                "changed": False,
            }
        temp_dir = data_dir / ".tmp-update"
        temp_dir.mkdir(parents=True, exist_ok=True)
        v4_temp = temp_dir / V4_FILENAME
        v6_temp = temp_dir / V6_FILENAME
        base = settings.ip2region_download_base_url.rstrip("/")
        try:
            _download_to(
                f"{base}/{latest}/data/{V4_FILENAME}", v4_temp,
                settings.ip2region_http_timeout_seconds,
            )
            _download_to(
                f"{base}/{latest}/data/{V6_FILENAME}", v6_temp,
                settings.ip2region_http_timeout_seconds,
            )
            result = install(data_dir, v4_temp, v6_temp, latest)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        result["changed"] = True
        if actor is not None:
            log_audit(
                db,
                "admin",
                str(actor.id),
                "admin_update_ip2region",
                category="admin_settings",
                target_type="ip2region",
                target_id=None,
                ip=request.client.host if request is not None and request.client else None,
                user_agent=request.headers.get("user-agent") if request is not None else None,
                detail={"version": latest},
            )
        return result
    finally:
        _update_lock.release()


def ip2region_status(db: Session) -> dict:
    settings = get_settings()
    data_dir = Path(settings.ip2region_data_dir)
    meta = read_meta(data_dir)
    v4_ready = (data_dir / V4_FILENAME).is_file()
    v6_ready = (data_dir / V6_FILENAME).is_file()
    return {
        "version": meta.get("version")
        or ("内置数据" if v4_ready and v6_ready else None),
        "data_updated_at": meta.get("data_updated_at")
        or data_timestamp(data_dir),
        "v4_ready": v4_ready,
        "v6_ready": v6_ready,
        "auto_update_enabled": get_site_setting_bool(
            db, AUTO_UPDATE_ENABLED_KEY, settings.ip2region_auto_update_enabled
        ),
        "update_interval_hours": get_site_setting_int(
            db, UPDATE_INTERVAL_HOURS_KEY, settings.ip2region_update_interval_hours
        ),
    }


def maybe_auto_update(db: Session) -> None:
    settings = get_settings()
    if not get_site_setting_bool(
        db, AUTO_UPDATE_ENABLED_KEY, settings.ip2region_auto_update_enabled
    ):
        return
    interval = get_site_setting_int(
        db, UPDATE_INTERVAL_HOURS_KEY, settings.ip2region_update_interval_hours
    )
    meta = read_meta(Path(settings.ip2region_data_dir))
    last_check = meta.get("last_check_at")
    if last_check:
        try:
            checked_at = datetime.fromisoformat(last_check)
            if (
                datetime.now(timezone.utc) - checked_at
            ).total_seconds() < interval * 3600:
                return
        except ValueError:
            pass
    try:
        result = update_ip2region(db)
        logger.info(
            "ip2region 自动更新完成：%s（changed=%s）",
            result["version"],
            result["changed"],
        )
    except Exception:
        logger.exception("ip2region 自动更新失败")
```

- [ ] **Step 4:** `scripts/download_ip2region.py`（纯标准库，供 Docker 构建与本地开发）：

```python
#!/usr/bin/env python3
"""下载固定 tag 的 ip2region xdb 数据并写 meta.json（SHA256 校验）。"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

DEFAULT_TAG = "v3.17.0"
DEFAULT_BASE = "https://raw.githubusercontent.com/lionsoul2014/ip2region"
PINNED_SHA256 = {
    ("v3.17.0", "ip2region_v4.xdb"):
        "6307a9696f5711f84bcb8b25f07894de68a64a0ed4a1cc7e990562dd3084f210",
    ("v3.17.0", "ip2region_v6.xdb"):
        "5b93da35ac28bc316dccc54a758381f7a874ae0461dd51ff5df5e34815586f11",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default=DEFAULT_TAG)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--data-dir", default="data/ip2region")
    args = parser.parse_args()
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("ip2region_v4.xdb", "ip2region_v6.xdb"):
        url = f"{args.base_url.rstrip('/')}/{args.tag}/data/{filename}"
        temp = data_dir / f"{filename}.tmp"
        print(f"下载 {url}", file=sys.stderr)
        with urllib.request.urlopen(url, timeout=60) as response, open(temp, "wb") as out:
            shutil.copyfileobj(response, out)
        digest = hashlib.sha256(temp.read_bytes()).hexdigest()
        expected = PINNED_SHA256.get((args.tag, filename))
        if expected and digest != expected:
            temp.unlink()
            raise SystemExit(f"SHA256 校验失败：{filename}（{digest}）")
        os.replace(temp, data_dir / filename)
    meta = {
        "version": args.tag,
        "data_updated_at": None,
        "last_check_at": None,
    }
    (data_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"完成：{data_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5:** Run: `cd backend && .venv/bin/python -m pytest tests/test_ip2region_update.py -q` → PASS。
- [ ] **Step 6:** 本地冒烟：`.venv/bin/python scripts/download_ip2region.py` 把两份 xdb 放入 `backend/data/ip2region/`，随后 `.venv/bin/python -c "from app.services.geoip import describe_ip; print(describe_ip('223.104.60.77'))"` → `广东省 深圳市`。

---

## Task 7: 站点设置路由扩展与手动更新端点

**Files:**
- Modify: `backend/app/api/routes/admin_settings.py`
- Test: `backend/tests/test_admin_settings.py`

**Interfaces:**
- Consumes: `ip2region_status`、`update_ip2region`（Task 6）、`set_site_setting_bool/int`、限流器
- Produces: `GET /settings` → `{public_registration_enabled, ip2region}`；`PUT /settings` 扩展；`POST /settings/ip2region/update`

- [ ] **Step 1: 写失败测试**：更新 `test_admin_settings.py` 的 GET 断言为包含 `ip2region` 键；新增用例：非管理员 PUT/update 均 403；PUT 传 `ip2region_auto_update_enabled=True` + `ip2region_update_interval_hours=48` 后 GET 反映；monkeypatch `update_ip2region` 返回 `{"version":"v9","data_updated_at":"t","changed":True}` 后 POST 返回 200 且审计记录 `admin_update_ip2region`。
- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** 重写 `admin_settings.py`：

```python
class SiteSettingsUpdate(BaseModel):
    public_registration_enabled: bool
    ip2region_auto_update_enabled: bool | None = None
    ip2region_update_interval_hours: int | None = Field(None, ge=1, le=8760)
```

GET 返回 `{..., "ip2region": ip2region_status(db)}`；PUT 依次应用非 None 的新键（`set_site_setting_bool/int`），审计 `detail` 记录所有变更键，返回与 GET 同构。新增：

```python
@router.post("/settings/ip2region/update", response_model=dict)
def update_ip2region_db(
    request: Request,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    """立即检查并更新 ip2region 离线库；已是最新时 changed=false。"""
    settings = get_settings()
    count = get_rate_limiter().hit(
        "admin_ip2region_update",
        str(actor.id),
        settings.ip2region_update_rate_window_seconds,
    )
    if count > settings.ip2region_update_rate_limit:
        log_rate_limit_rejected_once(
            db, "admin_ip2region_update", count,
            settings.ip2region_update_rate_limit,
            actor_type="admin", actor_id=str(actor.id),
            detail={"action": "admin_ip2region_update", "reason": "rate_limit"},
        )
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "操作过于频繁，请稍后再试")
    try:
        return update_ip2region(db, actor=actor, request=request)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"检查或下载最新 IP 库失败：{exc}"
        ) from exc
```

imports 补 `HTTPException, status`、`get_rate_limiter`、`log_rate_limit_rejected_once`、`update_ip2region as update_ip2region_service`、`ip2region_status`、`get_site_setting_int/set_site_setting_int`。

- [ ] **Step 4:** Run: `cd backend && .venv/bin/python -m pytest tests/test_admin_settings.py tests/test_admin_users_management.py -q` → PASS

---

## Task 8: 自动更新后台任务与部署接线

**Files:**
- Modify: `backend/app/main.py`、`docker-compose.yaml`、`.env.example`、`backend/Dockerfile`、`docs/deployment.md`

**Interfaces:**
- Consumes: `maybe_auto_update`（Task 6）

- [ ] **Step 1:** `main.py` 增加：

```python
from app.services.ip2region_update import maybe_auto_update


def _run_ip2region_update(app: FastAPI) -> None:
    try:
        dependency = app.dependency_overrides.get(get_db, get_db)
        db = next(dependency())
        try:
            maybe_auto_update(db)
        finally:
            db.close()
    except Exception:
        logger.exception("ip2region 自动更新检查失败")


async def _ip2region_update_loop(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(3600)
        await asyncio.to_thread(_run_ip2region_update, app)
```

lifespan 中始终 `task = asyncio.create_task(_ip2region_update_loop(app))`，退出时 cancel + suppress `CancelledError`。

- [ ] **Step 2:** `docker-compose.yaml` backend `environment` 追加：

```yaml
      IP2REGION_DATA_DIR: ${IP2REGION_DATA_DIR:-/app/data/ip2region}
      IP2REGION_AUTO_UPDATE_ENABLED: ${IP2REGION_AUTO_UPDATE_ENABLED:-false}
      IP2REGION_UPDATE_INTERVAL_HOURS: ${IP2REGION_UPDATE_INTERVAL_HOURS:-24}
      IP2REGION_RELEASES_API_URL: ${IP2REGION_RELEASES_API_URL:-https://api.github.com/repos/lionsoul2014/ip2region/releases/latest}
      IP2REGION_DOWNLOAD_BASE_URL: ${IP2REGION_DOWNLOAD_BASE_URL:-https://raw.githubusercontent.com/lionsoul2014/ip2region}
```

- [ ] **Step 3:** `backend/Dockerfile` 在 `COPY scripts ./scripts` 后加：

```dockerfile
RUN mkdir -p /app/data/ip2region \
    && python scripts/download_ip2region.py --data-dir /app/data/ip2region
```

并把 `chown -R 10001:10001 /app` 覆盖 `/app/data`（已有该行）。

- [ ] **Step 4:** `.env.example` 追加上述变量及注释；`docs/deployment.md` 增补「IP 归属地库」小节（用途、48MB 内存口径、镜像切换与自动更新说明）。
- [ ] **Step 5:** Run: `cd backend && .venv/bin/python -m pytest -q` → 全绿（lifespan 任务不影响测试）。

---

## Task 9: 前端类型与 API 客户端

**Files:**
- Modify: `frontend/src/api/types.ts`、`frontend/src/api/client.ts`

**Interfaces:**
- Produces: `AdminSessionOut.ip_location: string | null`、`AuditLogOut.ip_location: string | null`、`AdminStats.regions: AdminStatsRegion[]`、`AdminStatsRegion {region,count}`、`Ip2regionStatus`、`SiteSettings.ip2region`、`Ip2regionUpdateResult`、`SiteSettingsUpdate`、`adminSettingsApi.ip2regionUpdate()`

- [ ] `types.ts`：按上述补齐；`SiteSettingsUpdate` 放 `client.ts`（与现有 `SiteSettings` 区分）。
- [ ] `client.ts`：`adminSettingsApi` 增 `ip2regionUpdate: () => api<Ip2regionUpdateResult>("/api/v1/admin/settings/ip2region/update", { method: "POST" })`；`update(payload: SiteSettingsUpdate)`。
- [ ] Run: `cd frontend && npx tsc -b` → PASS（后续面板接入前类型先行编译通过）。

---

## Task 10: 会话/审计面板展示归属地

**Files:**
- Modify: `frontend/src/pages/AdminSessionsPanel.tsx`、`frontend/src/pages/AdminAuditPanel.tsx`
- Test: `frontend/src/__tests__/AdminSessionsPanel.test.tsx`、`AdminAuditPanel.test.tsx`

- [ ] **Step 1: 写失败测试**：`sessionOut()` 增 `ip_location: "广东省 深圳市"`，断言列表出现该文本；审计 mock 增 `ip_location: "内网地址"`，断言出现。
- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** 会话 IP 单元格：

```tsx
<td>
  <div className="truncate" title={session.ip ?? undefined}>
    {session.ip || "—"}
  </div>
  {session.ip_location && (
    <div className="truncate text-xs text-muted">
      {session.ip_location}
    </div>
  )}
</td>
```

审计 IP 列：

```tsx
<td>
  <div>{log.ip ?? "-"}</div>
  {log.ip_location && (
    <div className="text-xs text-muted">{log.ip_location}</div>
  )}
</td>
```

- [ ] **Step 4:** Run: `cd frontend && npm test -- AdminSessionsPanel AdminAuditPanel` → PASS

---

## Task 11: 统计面板地域分布

**Files:**
- Modify: `frontend/src/pages/AdminStatsPanel.tsx`
- Test: `frontend/src/__tests__/AdminStatsPanel.test.tsx`

- [ ] **Step 1: 写失败测试**：`statsBody` 增 `regions: [{region:"广东省 深圳市",count:12},{region:"其它",count:3}]`；断言出现「登录来源地域分布」「广东省 深圳市」「12」与「其它」。
- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** 在现有 `lg:grid-cols-3` 网格后加卡片：

```tsx
<div className="card p-5">
  <p className="mb-3 text-sm text-muted">
    登录来源地域分布（近 {days} 天，Top 10）
  </p>
  {stats.regions.length === 0 ? (
    <p className="text-sm text-muted">
      暂无数据：IP 库未安装或统计窗口内无登录。
    </p>
  ) : (
    <div className="space-y-2.5">
      {stats.regions.map((item) => (
        <div key={item.region} className="flex items-center gap-3 text-sm">
          <span className="w-32 shrink-0 truncate text-muted" title={item.region}>
            {item.region}
          </span>
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${(item.count / maxRegionCount) * 100}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-foreground">
            {numberFormat.format(item.count)}
          </span>
        </div>
      ))}
    </div>
  )}
</div>
```

`maxRegionCount = Math.max(1, ...stats.regions.map(r => r.count))`。

- [ ] **Step 4:** Run: `cd frontend && npm test -- AdminStatsPanel` → PASS

---

## Task 12: 站点设置 IP 库卡片

**Files:**
- Modify: `frontend/src/pages/AdminSettingsPanel.tsx`
- Test: `frontend/src/__tests__/AdminSettingsPanel.test.tsx`（新建）

- [ ] **Step 1: 写失败测试**：GET mock 返回 `public_registration_enabled: true, ip2region: {...}`；断言渲染版本、加载状态、「自动更新」按钮；点击自动更新断言 PUT 载荷含 `ip2region_auto_update_enabled: true`；改间隔下拉断言 PUT 载荷含 `ip2region_update_interval_hours: 48`；点击「立即检查更新」断言 POST `/settings/ip2region/update` 且成功 Toast。
- [ ] **Step 2:** Run → FAIL
- [ ] **Step 3:** 实现卡片：

```tsx
const UPDATE_INTERVALS = [
  { hours: 12, label: "每 12 小时" },
  { hours: 24, label: "每 24 小时" },
  { hours: 72, label: "每 3 天" },
  { hours: 168, label: "每 7 天" },
] as const;
```

状态行：`版本 {version ?? "未安装"} · 数据 {date ?? "未知"}` + `IPv4/IPv6 {ready ? "已加载" : "未加载"}`。自动更新按钮 `AsyncButton`（onClick → `adminSettingsApi.update({public_registration_enabled, ip2region_auto_update_enabled: !enabled})` 后 `setSettings(updated)` + Toast）。间隔 `<select value={...} onChange={...}>`（更新后 Toast）。更新按钮：`updateAction = useAsyncAction(async () => { const result = await adminSettingsApi.ip2regionUpdate(); await reload(); toast.success(result.changed ? `已更新到 ${result.version}` : `已是最新版本 ${result.version}`); })`；失败走 `onError` Toast。

- [ ] **Step 4:** Run: `cd frontend && npm test -- AdminSettingsPanel` → PASS

---

## Task 13: 文档、CHANGELOG 与全量验证

**Files:**
- Modify: `CHANGELOG.md`

- [ ] `CHANGELOG.md`「未发布（开发中）」的「行为变更」追加：IP 归属地展示（会话监控/审计日志）、数据统计新增登录来源地域分布、站点设置新增 ip2region 库手动/自动更新（引用本 spec 与部署文档）。
- [ ] Run 后端: `cd backend && .venv/bin/python -m pytest -q` → 全绿
- [ ] Run 前端: `cd frontend && npx tsc -b && npm run lint && npm test && npm run build` → 全绿
- [ ] 手动冒烟（本机已放 xdb）：`describe_ip` 国内/海外/内网/保留各一例；`GET /api/v1/admin/settings` 返回 `ip2region` 状态。

---

## 执行方式

本会话按 **Inline Execution** 执行（协作模式禁止未经请求派生子代理），用 superpowers:executing-plans 的核对方式逐任务推进；每完成一个任务运行对应测试后再进入下一个任务。
