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
