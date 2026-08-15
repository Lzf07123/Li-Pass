"""待确认登出请求存储：end_session 确认页与确认 API 之间共享的短生命周期状态。"""

import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.redis import get_redis_client


@dataclass
class PendingLogoutRequest:
    client_id: str
    post_logout_redirect_uri: str | None
    state: str | None
    sid: str
    sub: str
    client_name: str


class LogoutRequestStore:
    def create(
        self, request: PendingLogoutRequest, ttl_seconds: int = 600
    ) -> str:
        raise NotImplementedError

    def get(self, request_id: str) -> PendingLogoutRequest | None:
        raise NotImplementedError

    def delete(self, request_id: str) -> None:
        raise NotImplementedError


class InMemoryLogoutRequestStore(LogoutRequestStore):
    MAX_ITEMS = 1_000

    def __init__(self) -> None:
        self._items: dict[str, tuple[PendingLogoutRequest, datetime]] = {}

    def create(
        self, request: PendingLogoutRequest, ttl_seconds: int = 600
    ) -> str:
        self._sweep()
        request_id = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._items[request_id] = (request, expires)
        return request_id

    def _sweep(self) -> None:
        if len(self._items) < self.MAX_ITEMS:
            return
        now = datetime.now(timezone.utc)
        expired = [k for k, (_, exp) in self._items.items() if exp < now]
        for key in expired:
            self._items.pop(key, None)

    def get(self, request_id: str) -> PendingLogoutRequest | None:
        item = self._items.get(request_id)
        if item is None:
            return None
        request, expires = item
        if expires < datetime.now(timezone.utc):
            self._items.pop(request_id, None)
            return None
        return request

    def delete(self, request_id: str) -> None:
        self._items.pop(request_id, None)


class RedisLogoutRequestStore(LogoutRequestStore):
    def __init__(self, client) -> None:
        self._client = client

    def _key(self, request_id: str) -> str:
        return f"logout-request:{request_id}"

    def create(
        self, request: PendingLogoutRequest, ttl_seconds: int = 600
    ) -> str:
        request_id = secrets.token_urlsafe(24)
        self._client.setex(
            self._key(request_id), ttl_seconds, json.dumps(asdict(request))
        )
        return request_id

    def get(self, request_id: str) -> PendingLogoutRequest | None:
        raw = self._client.get(self._key(request_id))
        if raw is None:
            return None
        return PendingLogoutRequest(**json.loads(raw))

    def delete(self, request_id: str) -> None:
        self._client.delete(self._key(request_id))


_memory_store = InMemoryLogoutRequestStore()


def get_logout_request_store() -> LogoutRequestStore:
    settings = get_settings()
    if settings.pending_request_store == "memory":
        return _memory_store
    return RedisLogoutRequestStore(get_redis_client())
