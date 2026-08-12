import time

from app.core.config import get_settings
from app.core.redis import get_redis_client


class RateLimiter:
    def hit(
        self, scope: str, key: str, window_seconds: int, increment: int = 1
    ) -> int:
        raise NotImplementedError

    def reset(self, scope: str, key: str) -> None:
        raise NotImplementedError

    def decrement(self, scope: str, key: str) -> None:
        """撤销一次计数，用于邮件发送失败时不要把失败请求计入限流。"""
        raise NotImplementedError

    def remaining(self, scope: str, key: str) -> int:
        """返回当前限流剩余等待秒数（无记录/已过期返回 0）。"""
        raise NotImplementedError


class MemoryRateLimiter(RateLimiter):
    MAX_ITEMS = 10_000

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], tuple[int, float]] = {}

    def _prune(self, scope: str, key: str, now: float) -> None:
        item = self._items.get((scope, key))
        if item is not None and item[1] <= now:
            self._items.pop((scope, key), None)

    def _sweep(self, now: float) -> None:
        """条目超过阈值时清理全部过期项，防止攻击者用唯一键撑爆内存。"""
        if len(self._items) < self.MAX_ITEMS:
            return
        expired = [k for k, (_, expires) in self._items.items() if expires <= now]
        for key in expired:
            self._items.pop(key, None)

    def hit(
        self, scope: str, key: str, window_seconds: int, increment: int = 1
    ) -> int:
        now = time.monotonic()
        self._sweep(now)
        self._prune(scope, key, now)
        count, expires = self._items.get((scope, key), (0, now + window_seconds))
        count += increment
        self._items[(scope, key)] = (count, expires)
        return count

    def reset(self, scope: str, key: str) -> None:
        self._items.pop((scope, key), None)

    def decrement(self, scope: str, key: str) -> None:
        item = self._items.get((scope, key))
        if item is None:
            return
        count, expires = item
        if count <= 1:
            self._items.pop((scope, key), None)
        else:
            self._items[(scope, key)] = (count - 1, expires)

    def remaining(self, scope: str, key: str) -> int:
        item = self._items.get((scope, key))
        if item is None:
            return 0
        count, expires = item
        if count <= 0 or expires <= time.monotonic():
            return 0
        return max(1, int(expires - time.monotonic()))


class RedisRateLimiter(RateLimiter):
    def __init__(self, client) -> None:
        self._client = client

    def _key(self, scope: str, key: str) -> str:
        return f"rl:{scope}:{key}"

    def hit(
        self, scope: str, key: str, window_seconds: int, increment: int = 1
    ) -> int:
        redis_key = self._key(scope, key)
        count = self._client.incrby(redis_key, increment)
        if count == increment:
            self._client.expire(redis_key, window_seconds)
        return count

    def reset(self, scope: str, key: str) -> None:
        self._client.delete(self._key(scope, key))

    def decrement(self, scope: str, key: str) -> None:
        redis_key = self._key(scope, key)
        count = self._client.decrby(redis_key, 1)
        if count <= 0:
            self._client.delete(redis_key)

    def remaining(self, scope: str, key: str) -> int:
        ttl_ms = self._client.pttl(self._key(scope, key))
        if ttl_ms is None or ttl_ms <= 0:
            return 0
        return max(1, (ttl_ms + 999) // 1000)


_memory_limiter = MemoryRateLimiter()
_redis_limiter = None


def get_rate_limiter() -> RateLimiter:
    settings = get_settings()
    if settings.rate_limiter == "memory":
        return _memory_limiter
    global _redis_limiter
    if _redis_limiter is None:
        _redis_limiter = RedisRateLimiter(get_redis_client())
    return _redis_limiter
