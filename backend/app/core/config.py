from functools import lru_cache

from pydantic import model_validator
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
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_from_name: str = "Portal OSS"
    smtp_use_tls: bool = True
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

    @model_validator(mode="after")
    def _validate_production(self):
        if self.environment != "production":
            return self
        for field in ("jwt_issuer", "frontend_base_url", "database_url", "redis_url"):
            value = getattr(self, field)
            if not value or "localhost" in value or "127.0.0.1" in value:
                raise ValueError(f"{field} 在生产环境必须显式配置真实地址，禁止使用默认值")
        if self.email_backend != "smtp" or not self.smtp_host or not self.smtp_from:
            raise ValueError(
                "生产环境邮件必须配置 EMAIL_BACKEND=smtp 与 SMTP_HOST/SMTP_FROM"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
