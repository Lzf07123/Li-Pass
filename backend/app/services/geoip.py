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

# RFC 5737/3849 文档保留网段：Python 将其归为 is_private，但语义上属于保留地址，
# 与 ip2region 的 Reserved 口径一致。
_DOCUMENTATION_NETWORKS = (
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("2001:db8::/32"),
)


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
        address.is_multicast
        or address.is_reserved
        or any(address in network for network in _DOCUMENTATION_NETWORKS)
    ):
        return normalized, _RESERVED_LABEL
    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_unspecified
    ):
        return normalized, _INTERNAL_LABEL
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
        # 加载期校验文件结构/IP 版本，拒绝损坏或错位的数据文件，
        # 避免把解析崩溃留到查询阶段（届时会让管理端接口整体 500）。
        ip2region_util.verify_from_file(path)
        header = ip2region_util.load_header_from_file(path)
        if header.ipVersion != version.id:
            raise ValueError(f"{path} IP 版本与预期不符")
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
            except Exception as exc:
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
        except (ValueError, IndexError):
            # 数据损坏/越界时降级为“未知”，不让单条查询击穿整个接口。
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


def locate_ip(ip: str | None) -> tuple[GeoIpResult | None, str | None]:
    """返回 (归属地结果, 分类标签)：公共 IP 且库就绪时给出 country/province，
    否则给出 内网地址/保留地址/未知 标签；无法解析时结果与标签均为 None。"""
    if not ip:
        return None, "未知"
    normalized, label = normalize_ip(ip)
    if label:
        return None, label
    if normalized is None:
        return None, "未知"
    result = get_geoip_resolver().resolve(normalized)
    return result, None
