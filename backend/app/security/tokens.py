import hashlib
import secrets

from app.security.crypto import hmac_hex


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    # OTP 仅 6 位，裸 SHA-256 可秒级离线爆破，必须加服务端密钥（HMAC）。
    return hmac_hex(code)


def generate_client_id() -> str:
    return "cli_" + secrets.token_urlsafe(24)


def generate_client_secret() -> str:
    return secrets.token_urlsafe(48)
