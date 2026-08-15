"""联邦登出：回程地址安全校验与登出目标收集。"""

import ipaddress
import logging
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _is_unsafe_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_public_host(host: str) -> None:
    """生产环境拒绝回环/私网/链路本地地址，防 SSRF 打内网。

    开发环境放行，便于本地 demo（如 http://localhost:3001）。
    """
    if get_settings().environment != "production":
        return
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except socket.gaierror as exc:
            raise ValueError(f"回程地址域名无法解析: {host}") from exc
    else:
        addresses = {str(literal)}
    parsed_addresses = {ipaddress.ip_address(addr) for addr in addresses}
    if any(_is_unsafe_ip(addr) for addr in parsed_addresses):
        raise ValueError("回程地址不允许指向回环/私网/链路本地地址")


def assert_safe_backchannel_url(url: str) -> None:
    """校验 backchannel_logout_uri：仅 http/https（生产强制 https），
    且生产环境目标不得为回环/私网地址。"""
    settings = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("回程地址必须是 http/https 地址")
    if settings.environment == "production" and parsed.scheme != "https":
        raise ValueError("生产环境回程地址必须使用 https")
    host = parsed.hostname
    if not host:
        raise ValueError("回程地址缺少主机名")
    _assert_public_host(host)


@dataclass(frozen=True)
class LogoutTarget:
    uri: str
    client_id: str
    sid: str
    sub: str
