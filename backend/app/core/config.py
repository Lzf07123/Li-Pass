from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Portal OSS"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://portal:portal@localhost:5432/portal"
    redis_url: str = "redis://localhost:6379/0"
    session_cookie_name: str = "portal_session"
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    session_ttl_days: int = 30
    cors_origins: list[str] = ["http://localhost:5173"]
    email_backend: str = "console"
    frontend_base_url: str = "http://localhost:5173"
    jwt_issuer: str = "http://localhost:8000"
    jwt_private_key_path: str = "jwt_private.pem"
    oauth_access_token_ttl_minutes: int = 15
    oauth_id_token_ttl_minutes: int = 5
    oauth_code_ttl_minutes: int = 10
    pending_request_store: str = "memory"
    encryption_key_path: str = "encryption.key"
    twofa_store: str = "memory"
    rate_limiter: str = "memory"
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 900
    otp_send_limit: int = 5
    otp_send_window_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
