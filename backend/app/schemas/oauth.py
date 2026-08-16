import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings

# 本 IdP 实际支持的 scope 全集（与发现文档、userinfo/id_token 的 claims 裁剪一致）。
SUPPORTED_SCOPES = frozenset({"openid", "profile", "email"})


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


def _validate_scopes(value: list[str]) -> list[str]:
    """scope 必须是支持集的非空子集，且必须包含 openid。"""
    normalized = [scope.strip() for scope in value if scope.strip()]
    if not normalized or "openid" not in normalized:
        raise ValueError("scopes 必须包含 openid")
    unknown = set(normalized) - SUPPORTED_SCOPES
    if unknown:
        raise ValueError("不支持的 scope：" + ", ".join(sorted(unknown)))
    return normalized


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    logout_uri: str | None = Field(default=None, max_length=500)
    post_logout_redirect_uris: list[str] = Field(default_factory=list)
    backchannel_logout_uri: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] = Field(min_length=1)
    scopes: list[str] = Field(default=["openid", "profile", "email"])
    require_consent_every_time: bool = False
    public: bool = True

    @field_validator(
        "logo_url", "home_url", "logout_uri", "backchannel_logout_uri"
    )
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_web_url(value, "站点地址")

    @field_validator("post_logout_redirect_uris")
    @classmethod
    def _check_post_logout_redirect_uris(cls, value: list[str]) -> list[str]:
        normalized = [
            _validate_web_url(uri, "登出回跳地址") or "" for uri in value
        ]
        if len(normalized) != len(set(normalized)):
            raise ValueError("登出回跳地址不能重复")
        return normalized

    @field_validator("redirect_uris")
    @classmethod
    def _check_redirect_uris(cls, value: list[str]) -> list[str]:
        normalized = [_validate_web_url(uri, "回调地址") for uri in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("回调地址不能重复")
        return normalized

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, value: list[str]) -> list[str]:
        return _validate_scopes(value)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    logout_uri: str | None = Field(default=None, max_length=500)
    post_logout_redirect_uris: list[str] | None = None
    backchannel_logout_uri: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] | None = None
    scopes: list[str] | None = None
    require_consent_every_time: bool | None = None
    is_active: bool | None = None

    @field_validator(
        "logo_url", "home_url", "logout_uri", "backchannel_logout_uri"
    )
    @classmethod
    def _check_url(cls, value: str | None) -> str | None:
        return _validate_web_url(value, "站点地址")

    @field_validator("post_logout_redirect_uris")
    @classmethod
    def _check_post_logout_redirect_uris(
        cls, value: list[str] | None
    ) -> list[str] | None:
        if value is None:
            return value
        normalized = [
            _validate_web_url(uri, "登出回跳地址") or "" for uri in value
        ]
        if len(normalized) != len(set(normalized)):
            raise ValueError("登出回跳地址不能重复")
        return normalized

    @field_validator("redirect_uris")
    @classmethod
    def _check_redirect_uris(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        normalized = [_validate_web_url(uri, "回调地址") for uri in value]
        if not normalized:
            raise ValueError("回调地址不能为空")
        if len(normalized) != len(set(normalized)):
            raise ValueError("回调地址不能重复")
        return normalized

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        return _validate_scopes(value)


class ClientOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None
    logout_uri: str | None
    post_logout_redirect_uris: list[str]
    backchannel_logout_uri: str | None
    redirect_uris: list[str]
    scopes: list[str]
    require_consent_every_time: bool
    is_active: bool
    has_secret: bool
    created_at: datetime


class ClientSecretOut(BaseModel):
    client: ClientOut
    client_secret: str | None


class ClientBlockCreate(BaseModel):
    email: str | None = Field(default=None, max_length=320)
    user_id: uuid.UUID | None = None
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
        "post_logout_redirect_uris": client.post_logout_redirect_uris,
        "backchannel_logout_uri": client.backchannel_logout_uri,
        "redirect_uris": client.redirect_uris,
        "scopes": client.scopes,
        "require_consent_every_time": client.require_consent_every_time,
        "is_active": client.is_active,
        "has_secret": client.client_secret_hash is not None,
        "created_at": client.created_at,
    }
