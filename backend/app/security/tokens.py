import hashlib
import secrets


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def generate_client_id() -> str:
    return "cli_" + secrets.token_urlsafe(24)


def generate_client_secret() -> str:
    return secrets.token_urlsafe(48)
