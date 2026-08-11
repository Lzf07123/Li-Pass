from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.schemas.oauth import (
    ClientCreate,
    ClientSecretOut,
    ClientUpdate,
    serialize_client,
)
from app.security.tokens import generate_client_id, generate_client_secret, hash_token

router = APIRouter(
    prefix="/api/v1/admin/clients",
    tags=["admin-clients"],
    dependencies=[Depends(get_current_admin)],
)


@router.get("", response_model=list[dict])
def list_clients(db: Session = Depends(get_db)) -> list[dict]:
    clients = db.scalars(
        select(OAuthClient).order_by(OAuthClient.created_at.desc())
    ).all()
    return [serialize_client(c) for c in clients]


@router.post("", response_model=ClientSecretOut)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> dict:
    client_secret = None
    client_secret_hash = None
    if not payload.public:
        client_secret = generate_client_secret()
        client_secret_hash = hash_token(client_secret)
    client = OAuthClient(
        client_id=generate_client_id(),
        client_secret_hash=client_secret_hash,
        name=payload.name,
        description=payload.description,
        logo_url=payload.logo_url,
        redirect_uris=payload.redirect_uris,
        scopes=payload.scopes,
        require_consent_every_time=payload.require_consent_every_time,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return {"client": serialize_client(client), "client_secret": client_secret}


@router.get("/{client_id:uuid}", response_model=dict)
def get_client(client_id, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return serialize_client(client)


@router.patch("/{client_id:uuid}", response_model=dict)
def update_client(client_id, payload: ClientUpdate, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    return serialize_client(client)


@router.delete("/{client_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(client_id, db: Session = Depends(get_db)) -> None:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    db.delete(client)
    db.commit()


@router.post("/{client_id:uuid}/reset-secret", response_model=ClientSecretOut)
def reset_secret(client_id, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    if client.client_secret_hash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "公开客户端没有密钥")
    client_secret = generate_client_secret()
    client.client_secret_hash = hash_token(client_secret)
    db.commit()
    return {"client": serialize_client(client), "client_secret": client_secret}
