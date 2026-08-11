import json
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import redis

from app.core.config import get_settings


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
    def __init__(self) -> None:
        self._items: dict[str, tuple[PendingAuthRequest, datetime]] = {}

    def create(self, request: PendingAuthRequest, ttl_seconds: int = 600) -> str:
        request_id = secrets.token_urlsafe(24)
        expires = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        self._items[request_id] = (request, expires)
        return request_id

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
    def __init__(self, client: redis.Redis) -> None:
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
        return InMemoryPendingRequestStore()
    if settings.pending_request_store == "redis":
        return RedisPendingRequestStore(
            redis.Redis.from_url(settings.redis_url, decode_responses=True)
        )
    raise ValueError(f"Unsupported pending request store: {settings.pending_request_store}")
