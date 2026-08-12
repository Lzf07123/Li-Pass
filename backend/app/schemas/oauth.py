from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings


def _validate_web_url(value: str | None, field_name: str) -> str | None:
    """校验 OAuth 客户端 URL 字段：仅 http/https、无凭据、无 # 片段。

    生产环境强制 https，防止 javascript:/data:/file: 等值进入
    授权跳转与前端渲染（href/src/window.location）链路。
    """
    if value is None:
        return value
    value = value.strip()
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{field_name} 必须是 http/https 地址")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{field_name} 不允许包含用户名或密码")
    if parsed.fragment:
        raise ValueError(f"{field_name} 不允许包含 # 片段")
    if get_settings().environment == "production" and parsed.scheme != "https":
        raise ValueError(f"生产环境 {field_name} 必须使用 https")
    return value


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    logout_uri: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] = Field(min_length=1)
    scopes: list[str] = Field(default=["openid", "profile", "email"])
    require_consent_every_time: bool = False
    public: bool = True

    @field_validator("logo_url", "home_url", "logout_uri")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_web_url(value, "站点地址")

    @field_validator("redirect_uris")
    @classmethod
    def _check_redirect_uris(cls, value: list[str]) -> list[str]:
        normalized = [_validate_web_url(uri, "回调地址") for uri in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("回调地址不能重复")
        return normalized


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    logout_uri: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] | None = None
    scopes: list[str] | None = None
    require_consent_every_time: bool | None = None
    is_active: bool | None = None

    @field_validator("logo_url", "home_url", "logout_uri")
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_web_url(value, "站点地址")

    @field_validator("redirect_uris")
    @classmethod
    def _check_redirect_uris(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [_validate_web_url(uri, "回调地址") for uri in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("回调地址不能重复")
        return normalized


class ClientOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None
    logout_uri: str | None
    redirect_uris: list[str]
    scopes: list[str]
    require_consent_every_time: bool
    is_active: bool
    created_at: datetime


class ClientSecretOut(BaseModel):
    client: ClientOut
    client_secret: str | None


class ClientBlockCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    user_id: str | None = None
    reason: str = Field(default="", max_length=500)


class ClientBlockOut(BaseModel):
    id: str
    user_id: str | None
    email: str | None
    reason: str
    created_at: datetime


def serialize_client(client) -> dict:
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "name": client.name,
        "description": client.description,
        "logo_url": client.logo_url,
        "home_url": client.home_url,
        "logout_uri": client.logout_uri,
        "redirect_uris": client.redirect_uris,
        "scopes": client.scopes,
        "require_consent_every_time": client.require_consent_every_time,
        "is_active": client.is_active,
        "created_at": client.created_at,
    }
