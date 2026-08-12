import time

import redis

from app.core.config import get_settings


class RateLimiter:
    def hit(self, scope: str, key: str, window_seconds: int) -> int:
        raise NotImplementedError

    def reset(self, scope: str, key: str) -> None:
        raise NotImplementedError


class MemoryRateLimiter(RateLimiter):
    def __init__(self) -> None:
        self._items: dict[tuple[str, str], tuple[int, float]] = {}

    def _prune(self, scope: str, key: str, now: float) -> None:
        item = self._items.get((scope, key))
        if item is not None and item[1] <= now:
            self._items.pop((scope, key), None)

    def hit(self, scope: str, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        self._prune(scope, key, now)
        count, expires = self._items.get((scope, key), (0, now + window_seconds))
        count += 1
        self._items[(scope, key)] = (count, expires)
        return count

    def reset(self, scope: str, key: str) -> None:
        self._items.pop((scope, key), None)


class RedisRateLimiter(RateLimiter):
    def __init__(self, client) -> None:
        self._client = client

    def _key(self, scope: str, key: str) -> str:
        return f"rl:{scope}:{key}"

    def hit(self, scope: str, key: str, window_seconds: int) -> int:
        redis_key = self._key(scope, key)
        count = self._client.incr(redis_key)
        if count == 1:
            self._client.expire(redis_key, window_seconds)
        return count

    def reset(self, scope: str, key: str) -> None:
        self._client.delete(self._key(scope, key))


_memory_limiter = MemoryRateLimiter()
_redis_limiter = None


def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    if settings.rate_limiter == "memory":
        return _memory_limiter
    global _redis_limiter
    if _redis_limiter is None:
        _redis_limiter = RedisRateLimiter(
            redis.Redis.from_url(settings.redis_url, decode_responses=True)
        )
    return _redis_limiter
