import redis

from app.core.config import get_settings

_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """返回进程级共享的 Redis 连接。

    限流器、2FA 挑战、待授权请求和就绪检查此前各自新建连接，
    同一进程会持有 3–4 条 Redis TCP 连接；统一为单连接后显著降低
    连接数与文件描述符占用（多 worker 部署时每个 worker 仍各持一条）。
    socket 超时设为 2 秒，Redis 故障时请求快速失败，避免默认无限等待
    拖垮健康检查与业务接口。
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            get_settings().redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )
    return _client
