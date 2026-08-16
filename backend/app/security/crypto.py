import hashlib
import hmac
import os
import time
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import get_settings


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """独占创建密钥文件，已存在则跳过。

    多 worker 首次启动时会同时尝试生成密钥；O_CREAT|O_EXCL 保证
    只有一个进程写入，其余进程复用现有文件，避免各自生成不同密钥。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)
    os.chmod(path, 0o600)


def read_key_bytes_with_retry(path: Path, attempts: int = 20, delay: float = 0.05) -> bytes:
    """读取密钥文件；文件刚被其他进程创建时可能读到不完整内容，短暂重试。"""
    last_error: Exception | None = None
    for _ in range(attempts):
        try:
            return path.read_bytes()
        except OSError as exc:
            last_error = exc
            time.sleep(delay)
    if last_error is not None:
        raise last_error
    raise OSError(f"无法读取密钥文件: {path}")


@lru_cache
def _fernet(path: str) -> Fernet:
    key_path = Path(path)
    if not key_path.exists():
        atomic_write_bytes(key_path, Fernet.generate_key())
    last_error: Exception | None = None
    for _ in range(20):
        try:
            return Fernet(read_key_bytes_with_retry(key_path))
        except (ValueError, TypeError) as exc:
            last_error = exc
            time.sleep(0.05)
    if last_error is not None:
        raise last_error
    raise ValueError(f"无法加载加密密钥: {path}")


def encrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).encrypt(value.encode()).decode()


def decrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).decrypt(value.encode()).decode()


@lru_cache
def _hmac_key(path: str) -> bytes:
    # 与 Fernet 数据加密密钥做域分离：从同一主密钥派生独立的 HMAC 密钥，
    # 避免 AES 加密与 OTP/恢复码认证共用同一密钥材料。
    _fernet(path)
    master = read_key_bytes_with_retry(Path(path))
    return hmac.new(master, b"lipass:hmac:v2", hashlib.sha256).digest()


def hmac_hex(value: str) -> str:
    """对低熵值（OTP、恢复码）做带服务端密钥的 HMAC-SHA256，防止数据库泄露后离线爆破。"""
    key = _hmac_key(get_settings().encryption_key_path)
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
