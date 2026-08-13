from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_otp_code, generate_token, hash_otp_code, hash_token


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("password123")
    assert password_hash != "password123"
    assert verify_password("password123", password_hash) is True
    assert verify_password("wrong", password_hash) is False


def test_verify_password_invalid_hash_returns_false() -> None:
    assert verify_password("password123", "not-a-valid-argon2-hash") is False


def test_token_and_otp_hashing() -> None:
    token = generate_token()
    assert len(token) >= 32
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token

    code = generate_otp_code()
    assert len(code) == 6 and code.isdigit()
    assert hash_otp_code(code) == hash_otp_code(code)
