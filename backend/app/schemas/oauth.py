from datetime import datetime

from pydantic import BaseModel, Field


class ClientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] = Field(min_length=1)
    scopes: list[str] = Field(default=["openid", "profile", "email"])
    require_consent_every_time: bool = False
    public: bool = True


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    home_url: str | None = Field(default=None, max_length=500)
    redirect_uris: list[str] | None = None
    scopes: list[str] | None = None
    require_consent_every_time: bool | None = None
    is_active: bool | None = None


class ClientOut(BaseModel):
    id: str
    client_id: str
    name: str
    description: str
    logo_url: str | None
    home_url: str | None
    redirect_uris: list[str]
    scopes: list[str]
    require_consent_every_time: bool
    is_active: bool
    created_at: datetime


class ClientSecretOut(BaseModel):
    client: ClientOut
    client_secret: str | None


def serialize_client(client) -> dict:
    return {
        "id": str(client.id),
        "client_id": client.client_id,
        "name": client.name,
        "description": client.description,
        "logo_url": client.logo_url,
        "home_url": client.home_url,
        "redirect_uris": client.redirect_uris,
        "scopes": client.scopes,
        "require_consent_every_time": client.require_consent_every_time,
        "is_active": client.is_active,
        "created_at": client.created_at,
    }
