from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """哈希参数升级（内存/迭代次数变化）后，登录成功时自动滚动到新参数。"""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False
