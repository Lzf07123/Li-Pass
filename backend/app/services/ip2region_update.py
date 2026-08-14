"""ip2region 离线库的状态、下载、校验、原子替换与自动更新调度。"""

import contextlib
import fcntl
import hashlib
import hmac
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.audit import log_audit
from app.services.geoip import reload_geoip_resolver
from app.services.ip2region_pins import PINNED_SHA256
from app.services.site_settings import (
    get_site_setting_bool,
    get_site_setting_int,
)
from ip2region import util as ip2region_util

logger = logging.getLogger(__name__)

HTTP_USER_AGENT = "Mozilla/5.0 (compatible; LinPass-SSO/1.0)"

V4_FILENAME = "ip2region_v4.xdb"
V6_FILENAME = "ip2region_v6.xdb"
META_FILENAME = "meta.json"
AUTO_UPDATE_ENABLED_KEY = "ip2region_auto_update_enabled"
UPDATE_INTERVAL_HOURS_KEY = "ip2region_update_interval_hours"


class UpdateInProgress(RuntimeError):
    """已有更新任务进行中（跨进程/线程互斥冲突）。"""


@contextlib.contextmanager
def _file_update_lock(data_dir: Path):
    """跨进程互斥：flock 对同一数据目录的更新任务串行化。

    此前是进程内 threading.Lock，UVICORN_WORKERS>1 时多个 worker 会并发
    写同一个 .tmp-update 目录。fcntl 锁同时覆盖线程与进程（Linux/macOS）。
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    lock_path = data_dir / ".update.lock"
    handle = lock_path.open("a+")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise UpdateInProgress("已有更新任务进行中") from None
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _http_get_json(url: str, timeout: float) -> dict:
    request = Request(url, headers={"User-Agent": HTTP_USER_AGENT})
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
    request = Request(url, headers={"User-Agent": HTTP_USER_AGENT})
    with urlopen(request, timeout=timeout) as response, open(
        destination, "wb"
    ) as out:
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
    """从 v4 文件头读取数据生成时间；缺失/损坏时返回 None。"""
    path = data_dir / V4_FILENAME
    try:
        header = ip2region_util.load_header_from_file(str(path))
        return datetime.fromtimestamp(header.createdAt, timezone.utc).isoformat()
    except Exception:
        return None


def _verify_pinned_hashes(
    v4_path: Path, v6_path: Path, version: str
) -> None:
    """校验下载文件与信任清单一致；未知版本或哈希不符一律拒绝。"""
    for filename, path in ((V4_FILENAME, v4_path), (V6_FILENAME, v6_path)):
        expected = PINNED_SHA256.get((version, filename))
        if expected is None:
            raise RuntimeError(
                f"版本 {version} 未列入信任清单，拒绝安装；"
                "请在应用升级后再更新 IP 库"
            )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if not hmac.compare_digest(digest, expected):
            raise ValueError(f"{filename} SHA256 校验失败，拒绝安装")


def install(data_dir: Path, v4_src: Path, v6_src: Path, version: str) -> dict:
    """校验候选文件并原子替换；任何失败都保留旧库。"""
    _verify_pinned_hashes(v4_src, v6_src, version)
    for source in (v4_src, v6_src):
        ip2region_util.verify_from_file(str(source))
    v4_header = ip2region_util.load_header_from_file(str(v4_src))
    v6_header = ip2region_util.load_header_from_file(str(v6_src))
    if v4_header.ipVersion != ip2region_util.XdbIPv4Id:
        raise ValueError("v4 文件头 IP 版本不匹配")
    if v6_header.ipVersion != ip2region_util.XdbIPv6Id:
        raise ValueError("v6 文件头 IP 版本不匹配")
    data_dir.mkdir(parents=True, exist_ok=True)
    v4_final = data_dir / V4_FILENAME
    v6_final = data_dir / V6_FILENAME
    v4_bak = data_dir / (V4_FILENAME + ".bak")
    v6_bak = data_dir / (V6_FILENAME + ".bak")
    for stale in (v4_bak, v6_bak):
        stale.unlink(missing_ok=True)
    had_v4 = v4_final.exists()
    had_v6 = v6_final.exists()
    # 先把旧库移到 .bak 再写入新库；任一替换失败即回滚，避免 v4/v6 版本错位。
    if had_v4:
        os.replace(v4_final, v4_bak)
    if had_v6:
        os.replace(v6_final, v6_bak)
    try:
        os.replace(v4_src, v4_final)
        os.replace(v6_src, v6_final)
    except BaseException:
        for final, bak, had in (
            (v4_final, v4_bak, had_v4),
            (v6_final, v6_bak, had_v6),
        ):
            final.unlink(missing_ok=True)
            if had and bak.exists():
                os.replace(bak, final)
        raise
    for bak in (v4_bak, v6_bak):
        bak.unlink(missing_ok=True)
    timestamp = datetime.fromtimestamp(
        v4_header.createdAt, timezone.utc
    ).isoformat()
    meta = read_meta(data_dir)
    meta.update(
        {
            "version": version,
            "data_updated_at": timestamp,
            "v4_sha256": hashlib.sha256(
                (data_dir / V4_FILENAME).read_bytes()
            ).hexdigest(),
            "v6_sha256": hashlib.sha256(
                (data_dir / V6_FILENAME).read_bytes()
            ).hexdigest(),
            "last_check_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_meta(data_dir, meta)
    reload_geoip_resolver()
    return {"version": version, "data_updated_at": timestamp}


def update_ip2region(db: Session, actor=None, request=None) -> dict:
    """检查最新版本，仅在落后时下载安装；返回 changed 标记。"""
    settings = get_settings()
    data_dir = Path(settings.ip2region_data_dir)
    with _file_update_lock(data_dir):
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
                f"{base}/{latest}/data/{V4_FILENAME}",
                v4_temp,
                settings.ip2region_http_timeout_seconds,
            )
            _download_to(
                f"{base}/{latest}/data/{V6_FILENAME}",
                v6_temp,
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
                ip=(
                    request.client.host
                    if request is not None and request.client
                    else None
                ),
                user_agent=(
                    request.headers.get("user-agent")
                    if request is not None
                    else None
                ),
                detail={"version": latest},
            )
        return result


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
            db,
            UPDATE_INTERVAL_HOURS_KEY,
            settings.ip2region_update_interval_hours,
        ),
    }


def maybe_auto_update(db: Session) -> None:
    """按站点设置决定是否执行自动更新；失败仅记日志。"""
    settings = get_settings()
    if not get_site_setting_bool(
        db, AUTO_UPDATE_ENABLED_KEY, settings.ip2region_auto_update_enabled
    ):
        return
    interval = get_site_setting_int(
        db, UPDATE_INTERVAL_HOURS_KEY, settings.ip2region_update_interval_hours
    )
    # 防御脏数据：0/负间隔会绕过“距上次检查不足间隔即跳过”的判断，
    # 退化为每小时都触发更新；钳制到最小 1 小时。
    interval = max(1, interval)
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
