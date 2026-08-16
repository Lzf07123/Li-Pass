import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()

# 与前端强度条「中」档一致：长度 ≥8 且 4 类字符（小写/大写/数字/符号）
# 至少命中 2 类。长度下限由 schema 的 min_length 单独约束。
_PASSWORD_CLASS_PATTERNS = (
    re.compile(r"[a-z]"),
    re.compile(r"[A-Z]"),
    re.compile(r"[0-9]"),
    re.compile(r"[^A-Za-z0-9]"),
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """哈希参数升级（内存/迭代次数变化）后，登录成功时自动滚动到新参数。"""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False


def password_meets_policy(password: str) -> bool:
    """服务端密码复杂度：4 类字符中至少命中 2 类。"""
    return (
        sum(bool(pattern.search(password)) for pattern in _PASSWORD_CLASS_PATTERNS)
        >= 2
    )


def validate_password_strength(password: str) -> str:
    """Pydantic 校验器复用入口：不满足复杂度时抛 ValueError（映射为 422）。"""
    if not password_meets_policy(password):
        raise ValueError("密码强度不足：至少包含字母、数字或符号中的两类")
    return password
