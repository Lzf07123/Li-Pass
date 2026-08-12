import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.core.redis import get_redis_client


@dataclass
class PendingAuthRequest:
    client_id: str
    redirect_uri: str
    scope: str
    state: str | None = None
    nonce: str | None = None
    code_challenge: str | None = None
    code_challenge_method: str = "S256"


class PendingRequestStore:
    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        raise NotImplementedError

    def get(self, request_id: str) -> PendingAuthRequest | None:
        raise NotImplementedError

    def delete(self, request_id: str) -> None:
        raise NotImplementedError


class InMemoryPendingRequestStore(PendingRequestStore):
    MAX_ITEMS = 1_000

    def __init__(self) -> None:
        self._items: dict[str, tuple[PendingAuthRequest, datetime]] = {}

    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
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

    def get(self, request_id: str) -> PendingAuthRequest | None:
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


class RedisPendingRequestStore(PendingRequestStore):
    def __init__(self, client) -> None:
        self._client = client

    def _key(self, request_id: str) -> str:
        return f"pending-auth:{request_id}"

    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        request_id = secrets.token_urlsafe(24)
        self._client.setex(
            self._key(request_id), ttl_seconds, json.dumps(asdict(request))
        )
        return request_id

    def get(self, request_id: str) -> PendingAuthRequest | None:
        raw = self._client.get(self._key(request_id))
        if raw is None:
            return None
        return PendingAuthRequest(**json.loads(raw))

    def delete(self, request_id: str) -> None:
        self._client.delete(self._key(request_id))


def get_pending_request_store() -> PendingRequestStore:
    settings = get_settings()
    if settings.pending_request_store == "memory":
        return _memory_store
    if settings.pending_request_store == "redis":
        global _redis_store
        if _redis_store is None:
            _redis_store = RedisPendingRequestStore(get_redis_client())
        return _redis_store
    raise ValueError(f"Unsupported pending request store: {settings.pending_request_store}")


_memory_store = InMemoryPendingRequestStore()
_redis_store = None
