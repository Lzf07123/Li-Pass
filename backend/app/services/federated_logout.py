"""联邦登出：回程地址安全校验与登出目标收集。"""

import ipaddress
import logging
import socket
import uuid
from dataclasses import dataclass
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.session import Session as SessionModel
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


def build_logout_funnel(uris: list[str], final_url: str) -> str:
    """把多个网站的登出入口串成一条 `?next=` 链，浏览器依序跳转后回最终页。

    RP 约定：收到 `next` 参数时在本地清会话后跳转过去；链从最后一个目标
    开始反向包一层，保证第一个跳的是 uris[0]。
    """
    chain = final_url
    for uri in reversed(uris):
        chain = f"{uri}?next={quote(chain, safe='')}"
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
    """取消授权时按 用户×客户端 收集：仅限仍活跃的门户会话。"""
    rows = db.execute(
        select(OIDCClientSession, OAuthClient)
        .join(OAuthClient, OIDCClientSession.client_id == OAuthClient.id)
        .join(SessionModel, OIDCClientSession.session_id == SessionModel.id)
        .where(
            OIDCClientSession.user_id == user_id,
            OIDCClientSession.client_id == client_id,
            OIDCClientSession.revoked_at.is_(None),
            SessionModel.revoked_at.is_(None),
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


def dispatch_backchannel_logout(
    targets: list[LogoutTarget], *, transport: httpx.BaseTransport | None = None
) -> dict[str, bool]:
    """向各客户端回程端点 POST logout_token；失败按配置重试。

    不抛出异常：单点失败只记录日志并返回 False，由调用方写审计；
    transport 仅测试注入（httpx.MockTransport），生产为 None。
    """
    settings = get_settings()
    results: dict[str, bool] = {}
    with httpx.Client(
        transport=transport,
        timeout=settings.backchannel_logout_timeout_seconds,
        follow_redirects=False,
    ) as http:
        for target in targets:
            try:
                assert_safe_backchannel_url(target.uri)
            except ValueError:
                logger.warning("跳过不安全的回程地址: %s", target.uri)
                results[target.client_id] = False
                continue
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
