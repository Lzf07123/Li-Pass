"""ip2region 更新任务的后台进度状态（memory/redis 双后端）。

单槽位：同一时刻最多一个更新任务在跑（下载层有跨进程文件锁互斥）。
内存模式要求单 worker（项目文档已约束）；生产使用 redis 时跨 worker 一致。
"""

import json
import threading
import time

from app.core.config import get_settings
from app.core.redis import get_redis_client

_STATUS_KEY = "ip2region_update_status"
_DEFAULT_TTL_SECONDS = 3600


def _idle() -> dict:
    return {
        "state": "idle",
        "stage": "idle",
        "downloaded_bytes": 0,
        "total_bytes": 0,
        "percent": 0.0,
        "version": None,
        "changed": None,
        "message": None,
        "started_at": None,
        "finished_at": None,
    }


class UpdateProgress:
    """一次更新任务的进度快照（可直接 JSON 序列化）。"""

    def __init__(
        self,
        state: str = "idle",
        stage: str = "idle",
        downloaded_bytes: int = 0,
        total_bytes: int = 0,
        percent: float = 0.0,
        version: str | None = None,
        changed: bool | None = None,
        message: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        self.state = state
        self.stage = stage
        self.downloaded_bytes = downloaded_bytes
        self.total_bytes = total_bytes
        self.percent = percent
        self.version = version
        self.changed = changed
        self.message = message
        self.started_at = started_at
        self.finished_at = finished_at

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "stage": self.stage,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "percent": self.percent,
            "version": self.version,
            "changed": self.changed,
            "message": self.message,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class MemoryProgressStore:
    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._data: dict | None = None
        self._expires_at = 0.0

    def get(self) -> dict:
        with self._lock:
            if self._data is None or time.monotonic() >= self._expires_at:
                return _idle()
            return dict(self._data)

    def set(self, progress: UpdateProgress) -> None:
        with self._lock:
            self._data = progress.to_dict()
            self._expires_at = time.monotonic() + self._ttl_seconds

    def reset(self) -> None:
        with self._lock:
            self._data = None
            self._expires_at = 0.0


class RedisProgressStore:
    def __init__(self, client, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def get(self) -> dict:
        raw = self._client.get(_STATUS_KEY)
        if raw is None:
            return _idle()
        try:
            payload = json.loads(raw)
        except ValueError:
            return _idle()
        return payload if isinstance(payload, dict) else _idle()

    def set(self, progress: UpdateProgress) -> None:
        self._client.set(
            _STATUS_KEY,
            json.dumps(progress.to_dict(), ensure_ascii=False),
            ex=self._ttl_seconds,
        )


_memory_store = MemoryProgressStore()
_redis_store = None


def get_progress_store():
    settings = get_settings()
    if settings.rate_limiter != "redis":
        return _memory_store
    global _redis_store
    if _redis_store is None:
        _redis_store = RedisProgressStore(get_redis_client())
    return _redis_store


def reset_progress_store() -> None:
    _memory_store.reset()
