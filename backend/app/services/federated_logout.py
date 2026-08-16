"""联邦登出：回程地址安全校验与登出目标收集。"""

import ipaddress
import logging
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from urllib.parse import quote, urlparse

import httpx
import httpcore
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.security.jwt import issue_logout_token

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


def _normalize_resolved_ip(
    addr: str,
) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    """把 IPv4-mapped IPv6 还原为 IPv4，避免 `::ffff:127.0.0.1` 绕过危险网段判断。"""
    parsed = ipaddress.ip_address(addr)
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed


def _validate_public_addresses(addresses: set[str] | list[str]) -> list[str]:
    """校验解析出的全部 IP 均为公网地址（防 SSRF 打内网），返回规范化地址列表。"""
    normalized = {_normalize_resolved_ip(addr) for addr in addresses}
    if any(_is_unsafe_ip(addr) for addr in normalized):
        raise ValueError("回程地址不允许指向回环/私网/链路本地地址")
    return sorted(str(addr) for addr in normalized)


def _resolve_public_host(host: str) -> list[str]:
    """把域名解析为 IP 列表并校验全部为公网地址（防 SSRF 打内网）。

    返回排序后的字符串地址列表，供连接层固定使用，消除「校验解析」与
    「实际连接」之间的 DNS rebinding 窗口。
    """
    host = host.rstrip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise ValueError(f"回程地址域名非法: {host}") from exc
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        try:
            addresses = {item[4][0] for item in socket.getaddrinfo(host, None)}
        except socket.gaierror as exc:
            raise ValueError(f"回程地址域名无法解析: {host}") from exc
    else:
        addresses = {str(literal)}
    return _validate_public_addresses(addresses)


def resolve_safe_backchannel_target(url: str) -> tuple[str, int, list[str]]:
    """校验回程登出地址并返回 (host, port, 固定 IP 列表)。

    仅 http/https（生产强制 https + 443）、不得携带用户名/密码与 # 片段；
    生产环境解析出的 IP 全部校验为公网地址后固定返回，开发环境返回空列表
    （不固定，便于本地 demo 如 http://localhost:3001）。
    """
    settings = get_settings()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("回程地址必须是 http/https 地址")
    if parsed.username or parsed.password:
        raise ValueError("回程地址不允许携带用户名或密码")
    if parsed.fragment:
        raise ValueError("回程地址不允许包含 # 片段")
    if settings.environment == "production":
        if parsed.scheme != "https":
            raise ValueError("生产环境回程地址必须使用 https")
        if parsed.port not in (None, 443):
            raise ValueError("生产环境回程地址必须使用 443 端口")
    host = parsed.hostname
    if not host:
        raise ValueError("回程地址缺少主机名")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if settings.environment != "production":
        return host, port, []
    return host, port, _resolve_public_host(host)


def assert_safe_backchannel_url(url: str) -> None:
    """校验 backchannel_logout_uri（管理端创建/更新时使用）。"""
    resolve_safe_backchannel_target(url)


class _PinnedDNSBackend(httpcore.SyncBackend):
    """DNS 固定：域名只拨号到安全校验时解析出的公网 IP 列表。

    TLS SNI 与证书校验仍使用原始域名（URL 未改写），因此不影响 HTTPS
    主机名校验；未固定的域名（开发环境）回退默认系统解析。
    """

    def __init__(self, pinned: dict[str, list[str]]) -> None:
        super().__init__()
        self._pinned = pinned

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options=None,
    ):
        addresses = self._pinned.get(host)
        if not addresses:
            return super().connect_tcp(
                host, port, timeout, local_address, socket_options
            )
        last_error: Exception | None = None
        for address in addresses:
            try:
                return super().connect_tcp(
                    address, port, timeout, local_address, socket_options
                )
            except httpcore.ConnectError as exc:
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError(f"无法连接回程登出地址: {host}")


_HTTPCORE_EXC_MAP: dict[type[Exception], type[httpx.HTTPError]] = {
    httpcore.TimeoutException: httpx.TimeoutException,
    httpcore.ConnectTimeout: httpx.ConnectTimeout,
    httpcore.ReadTimeout: httpx.ReadTimeout,
    httpcore.WriteTimeout: httpx.WriteTimeout,
    httpcore.PoolTimeout: httpx.PoolTimeout,
    httpcore.NetworkError: httpx.NetworkError,
    httpcore.ConnectError: httpx.ConnectError,
    httpcore.ReadError: httpx.ReadError,
    httpcore.WriteError: httpx.WriteError,
    httpcore.ProtocolError: httpx.ProtocolError,
    httpcore.LocalProtocolError: httpx.LocalProtocolError,
    httpcore.RemoteProtocolError: httpx.RemoteProtocolError,
}


class _ResponseStream(httpx.SyncByteStream):
    def __init__(self, stream) -> None:
        self._stream = stream

    def __iter__(self):
        yield from self._stream

    def close(self) -> None:
        if hasattr(self._stream, "close"):
            self._stream.close()


class _PinnedHostTransport(httpx.BaseTransport):
    """基于 httpcore 公开 API 的同步 transport，把 DNS 固定注入连接层。"""

    def __init__(self, backend: httpcore.NetworkBackend) -> None:
        self._pool = httpcore.ConnectionPool(network_backend=backend)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        assert isinstance(request.stream, httpx.SyncByteStream)
        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )
        try:
            resp = self._pool.handle_request(req)
        except Exception as exc:
            for source, target in _HTTPCORE_EXC_MAP.items():
                if isinstance(exc, source):
                    raise target(str(exc)) from exc
            raise
        assert isinstance(resp.stream, Iterable)
        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=_ResponseStream(resp.stream),
            extensions=resp.extensions,
        )

    def close(self) -> None:
        self._pool.close()


def build_logout_funnel(uris: list[str], final_url: str) -> str:
    """把多个网站的登出入口串成一条 `?next=` 链，浏览器依序跳转后回最终页。

    RP 约定：收到 `next` 参数时在本地清会话后跳转过去；链从最后一个目标
    开始反向包一层，保证第一个跳的是 uris[0]。
    """
    chain = final_url
    for uri in reversed(uris):
        separator = "&" if "?" in uri else "?"
        chain = f"{uri}{separator}next={quote(chain, safe='')}"
    return chain


@dataclass(frozen=True)
class LogoutTarget:
    uri: str
    client_id: str
    sid: str
    sub: str


def collect_logout_targets(
    db: Session, session_ids: list[uuid.UUID]
) -> list[LogoutTarget]:
    """查询给定门户会话在哪些客户端有活跃登录关系且配置了回程地址。"""
    if not session_ids:
        return []
    rows = db.execute(
        select(OIDCClientSession, OAuthClient)
        .join(OAuthClient, OIDCClientSession.client_id == OAuthClient.id)
        .where(
            OIDCClientSession.session_id.in_(session_ids),
            OIDCClientSession.revoked_at.is_(None),
            OAuthClient.is_active.is_(True),
            OAuthClient.backchannel_logout_uri.is_not(None),
            OAuthClient.backchannel_logout_uri != "",
        )
    ).all()
    return [
        LogoutTarget(
            uri=client.backchannel_logout_uri,
            client_id=client.client_id,
            sid=link.sid,
            sub=str(link.user_id),
        )
        for link, client in rows
    ]


def collect_logout_targets_for_user_client(
    db: Session, user_id: uuid.UUID, client_id: uuid.UUID
) -> list[LogoutTarget]:
    """取消授权时按 用户×客户端 收集全部未撤销链接。

    不要求门户会话仍活跃：即使门户会话已退出/被撤销，RP 本地会话仍可能
    存活（它绑定的是历史 sid），取消授权时同样要通知下线。
    """
    rows = db.execute(
        select(OIDCClientSession, OAuthClient)
        .join(OAuthClient, OIDCClientSession.client_id == OAuthClient.id)
        .where(
            OIDCClientSession.user_id == user_id,
            OIDCClientSession.client_id == client_id,
            OIDCClientSession.revoked_at.is_(None),
            OAuthClient.is_active.is_(True),
            OAuthClient.backchannel_logout_uri.is_not(None),
            OAuthClient.backchannel_logout_uri != "",
        )
    ).all()
    return [
        LogoutTarget(
            uri=client.backchannel_logout_uri,
            client_id=client.client_id,
            sid=link.sid,
            sub=str(link.user_id),
        )
        for link, client in rows
    ]


def collect_logout_targets_for_user(
    db: Session, user_id: uuid.UUID
) -> list[LogoutTarget]:
    """门户登出时按用户收集全部未撤销链接：跨会话通知所有已授权网站。

    不要求门户会话仍活跃：RP 本地会话绑定的是历史 sid，门户会话结束后
    可能仍存活，登出门户时同样要通知下线。
    """
    rows = db.execute(
        select(OIDCClientSession, OAuthClient)
        .join(OAuthClient, OIDCClientSession.client_id == OAuthClient.id)
        .where(
            OIDCClientSession.user_id == user_id,
            OIDCClientSession.revoked_at.is_(None),
            OAuthClient.is_active.is_(True),
            OAuthClient.backchannel_logout_uri.is_not(None),
            OAuthClient.backchannel_logout_uri != "",
        )
    ).all()
    return [
        LogoutTarget(
            uri=client.backchannel_logout_uri,
            client_id=client.client_id,
            sid=link.sid,
            sub=str(link.user_id),
        )
        for link, client in rows
    ]


def revoke_session_links(db: Session, session_ids: list[uuid.UUID]) -> int:
    """吊销若干门户会话对应的客户端登录链接（回程通知已派发后调用）。"""
    if not session_ids:
        return 0
    result = db.execute(
        update(OIDCClientSession)
        .where(
            OIDCClientSession.session_id.in_(session_ids),
            OIDCClientSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount or 0


def revoke_user_links(db: Session, user_id: uuid.UUID) -> int:
    """吊销某用户的全部客户端登录链接（门户登出已按用户通知所有授权）。"""
    result = db.execute(
        update(OIDCClientSession)
        .where(
            OIDCClientSession.user_id == user_id,
            OIDCClientSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    db.commit()
    return result.rowcount or 0


def dispatch_backchannel_logout(
    targets: list[LogoutTarget], *, transport: httpx.BaseTransport | None = None
) -> dict[str, bool]:
    """向各客户端回程端点 POST logout_token；失败按配置重试。

    不抛出异常：单点失败只记录日志并返回 False，由调用方写审计；
    transport 仅测试注入（httpx.MockTransport），生产为 None。
    """
    settings = get_settings()
    results: dict[str, bool] = {}
    for target in targets:
        try:
            host, _port, pinned = resolve_safe_backchannel_target(target.uri)
        except ValueError:
            logger.warning("跳过不安全的回程地址: %s", target.uri)
            results[target.client_id] = False
            continue
        effective_transport = transport
        if effective_transport is None:
            # 生产环境把 DNS 固定在安全校验的解析结果上，消除 rebinding 窗口；
            # 开发环境 pinned 为空，回退系统正常解析。
            effective_transport = _PinnedHostTransport(
                _PinnedDNSBackend({host: pinned})
            )
        with httpx.Client(
            transport=effective_transport,
            timeout=settings.backchannel_logout_timeout_seconds,
            follow_redirects=False,
        ) as http:
            token = issue_logout_token(target.sub, target.sid, target.client_id)
            delivered = False
            for attempt in range(settings.backchannel_logout_max_retries + 1):
                try:
                    response = http.post(
                        target.uri, data={"logout_token": token}
                    )
                except httpx.HTTPError as exc:
                    logger.warning(
                        "回程登出请求失败（第 %d 次）: %s %s",
                        attempt + 1,
                        target.uri,
                        exc,
                    )
                else:
                    if 200 <= response.status_code < 300:
                        delivered = True
                        break
                    logger.warning(
                        "回程登出返回 %d: %s",
                        response.status_code,
                        target.uri,
                    )
            results[target.client_id] = delivered
    return results
