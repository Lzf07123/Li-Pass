import hashlib
import hmac
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet

from app.core.config import get_settings


@lru_cache
def _fernet(path: str) -> Fernet:
    key_path = Path(path)
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_bytes(Fernet.generate_key())
        key_path.chmod(0o600)
    return Fernet(key_path.read_bytes())


def encrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).encrypt(value.encode()).decode()


def decrypt_str(value: str) -> str:
    return _fernet(get_settings().encryption_key_path).decrypt(value.encode()).decode()


@lru_cache
def _hmac_key(path: str) -> bytes:
    # 复用加密密钥文件：先确保文件存在，再读取原始字节作为 HMAC 密钥。
    _fernet(path)
    return Path(path).read_bytes()


def hmac_hex(value: str) -> str:
    """对低熵值（OTP、恢复码）做带服务端密钥的 HMAC-SHA256，防止数据库泄露后离线爆破。"""
    key = _hmac_key(get_settings().encryption_key_path)
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()
