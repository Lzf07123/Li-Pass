"""采集宿主机与当前进程的运行信息，供管理后台「系统信息」面板展示。

仅返回管理员可视范围内的基础指标（内存、磁盘、负载、运行时长等），
不采集任何用户数据或环境变量，避免敏感信息进入接口响应。
"""

import os
import platform
import socket
import time
from datetime import datetime, timezone

import fastapi
import psutil

from app.core.config import get_settings

_PROCESS_STARTED_AT = time.time()


def _module_version(module) -> str:
    return getattr(module, "__version__", "unknown")


def _load_average() -> list[float] | None:
    try:
        return list(os.getloadavg())
    except (AttributeError, OSError):
        return None


def collect_system_info() -> dict:
    """采集一次系统快照，返回可直接 JSON 序列化的结构。"""
    settings = get_settings()
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    process = psutil.Process()
    memory_info = process.memory_info()

    try:
        system_uptime_seconds = time.time() - psutil.boot_time()
    except (AttributeError, OSError):
        system_uptime_seconds = None

    load = _load_average()
    return {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "app": {
            "name": settings.app_name,
            "environment": settings.environment,
            "python_version": platform.python_version(),
            "fastapi_version": _module_version(fastapi),
        },
        "host": {
            "hostname": socket.gethostname(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "platform": platform.platform(),
            "cpu_cores": os.cpu_count(),
        },
        "load": {
            "avg_1m": load[0] if load else None,
            "avg_5m": load[1] if load else None,
            "avg_15m": load[2] if load else None,
        },
        "memory": {
            "total_bytes": vm.total,
            "used_bytes": vm.used,
            "available_bytes": vm.available,
            "percent": round(vm.percent, 1),
            "process_rss_bytes": memory_info.rss,
        },
        "disk": {
            "path": "/",
            "total_bytes": disk.total,
            "used_bytes": disk.used,
            "free_bytes": disk.free,
            "percent": round(disk.percent, 1),
        },
        "uptime": {
            "system_seconds": system_uptime_seconds,
            "process_seconds": time.time() - _PROCESS_STARTED_AT,
        },
        "process": {
            "pid": os.getpid(),
            "python_implementation": platform.python_implementation(),
        },
    }
