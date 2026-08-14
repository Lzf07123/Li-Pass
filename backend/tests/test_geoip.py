import struct

from app.services.geoip import GeoIpResolver, format_region, normalize_ip


def _fake_xdb(version: int, ip_version: int, body_size: int = 512) -> bytes:
    """构造最小合法 xdb 文件头（256 字节）+ 指定长度的数据体。"""
    header = struct.pack(
        "<HHIIIHH",
        version,  # structure version（3.0 或非法值）
        1,  # indexPolicy
        0,  # createdAt
        0,  # startIndexPtr
        0,  # endIndexPtr
        ip_version,  # 4=v4 / 6=v6
        4,  # runtimePtrBytes
    )
    return header.ljust(256, b"\x00") + b"\x01" * body_size


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


def test_resolve_corrupt_body_returns_none_instead_of_raising(tmp_path):
    """合法文件头 + 损坏数据体：解析必须降级返回 None，而不是 500。"""
    v4_path = tmp_path / "ip2region_v4.xdb"
    v6_path = tmp_path / "ip2region_v6.xdb"
    v4_path.write_bytes(_fake_xdb(3, 4, body_size=32))
    v6_path.write_bytes(_fake_xdb(3, 6, body_size=32))

    resolver = GeoIpResolver(v4_path, v6_path)

    assert resolver.is_ready() is True
    assert resolver.resolve("8.8.8.8") is None


def test_resolve_rejects_invalid_header_at_load(tmp_path):
    """非法结构版本的文件在加载期即被拒绝，解析返回 None。"""
    v4_path = tmp_path / "ip2region_v4.xdb"
    v6_path = tmp_path / "ip2region_v6.xdb"
    v4_path.write_bytes(_fake_xdb(9, 4))
    v6_path.write_bytes(_fake_xdb(9, 6))

    resolver = GeoIpResolver(v4_path, v6_path)

    assert resolver.is_ready() is False
    assert resolver.resolve("8.8.8.8") is None


def test_resolve_rejects_version_mismatch_at_load(tmp_path):
    """文件头 IP 版本与预期不符的文件在加载期即被拒绝。"""
    v4_path = tmp_path / "ip2region_v4.xdb"
    v6_path = tmp_path / "ip2region_v6.xdb"
    v4_path.write_bytes(_fake_xdb(3, 6))  # v4 路径放了 v6 数据
    v6_path.write_bytes(_fake_xdb(3, 6))

    resolver = GeoIpResolver(v4_path, v6_path)

    assert resolver.is_ready() is False
    assert resolver.resolve("8.8.8.8") is None
