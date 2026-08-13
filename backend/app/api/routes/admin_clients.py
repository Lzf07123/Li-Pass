import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.db import get_db
from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.schemas.auth import PasswordConfirm
from app.schemas.oauth import (
    ClientBlockCreate,
    ClientCreate,
    ClientSecretOut,
    ClientUpdate,
    serialize_client,
)
from app.security.passwords import verify_password
from app.security.tokens import generate_client_id, generate_client_secret, hash_token
from app.services.blocks import add_block, list_blocks, remove_block
from app.services.audit import log_audit

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
def create_client(
    payload: ClientCreate,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
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
        home_url=payload.home_url,
        redirect_uris=payload.redirect_uris,
        scopes=payload.scopes,
        require_consent_every_time=payload.require_consent_every_time,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_create_client",
        category="admin_client",
        target_type="oauth_client",
        target_id=str(client.id),
        detail={
            "name": client.name,
            "public": payload.public,
            "redirect_uris": client.redirect_uris,
        },
    )
    return {"client": serialize_client(client), "client_secret": client_secret}


@router.get("/{client_id:uuid}", response_model=dict)
def get_client(client_id: uuid.UUID, db: Session = Depends(get_db)) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return serialize_client(client)


@router.patch("/{client_id:uuid}", response_model=dict)
def update_client(
    client_id: uuid.UUID,
    payload: ClientUpdate,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    db.commit()
    db.refresh(client)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_update_client",
        category="admin_client",
        target_type="oauth_client",
        target_id=str(client.id),
        detail={"name": client.name, "is_active": client.is_active},
    )
    return serialize_client(client)


@router.delete("/{client_id:uuid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: uuid.UUID,
    payload: PasswordConfirm,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    if not verify_password(payload.current_password, actor.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_delete_client",
        category="admin_client",
        target_type="oauth_client",
        target_id=str(client.id),
        detail={"name": client.name, "client_id": client.client_id},
    )
    db.delete(client)
    db.commit()


@router.post("/{client_id:uuid}/reset-secret", response_model=ClientSecretOut)
def reset_secret(
    client_id,
    payload: PasswordConfirm,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    if not verify_password(payload.current_password, actor.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前密码错误")
    if client.client_secret_hash is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "公开客户端没有密钥")
    client_secret = generate_client_secret()
    client.client_secret_hash = hash_token(client_secret)
    db.commit()
    log_audit(
        db,
        "admin",
        str(actor.id),
        "admin_reset_client_secret",
        category="admin_client",
        target_type="oauth_client",
        target_id=str(client.id),
        detail={"name": client.name},
    )
    return {"client": serialize_client(client), "client_secret": client_secret}


def _serialize_block(block) -> dict:
    return {
        "id": str(block.id),
        "user_id": str(block.user_id) if block.user_id else None,
        "email": block.email,
        "reason": block.reason,
        "created_at": block.created_at,
    }


@router.get("/{client_id:uuid}/blocks", response_model=list[dict])
def admin_list_blocks(client_id: uuid.UUID, db: Session = Depends(get_db)) -> list[dict]:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return [_serialize_block(b) for b in list_blocks(db, client.id)]


@router.post("/{client_id:uuid}/blocks", response_model=dict)
def admin_add_block(
    client_id: uuid.UUID,
    payload: ClientBlockCreate,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> dict:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    try:
        block = add_block(
            db,
            client,
            email=payload.email,
            user_id=uuid.UUID(payload.user_id) if payload.user_id else None,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    log_audit(
        db,
        "admin",
        str(actor.id),
        "block_add",
        category="admin_block",
        target_type="oauth_client",
        target_id=str(client.id),
        detail={"email": block.email, "user_id": str(block.user_id) if block.user_id else None},
    )
    return _serialize_block(block)


@router.delete(
    "/{client_id:uuid}/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT
)
def admin_remove_block(
    client_id: uuid.UUID,
    block_id: uuid.UUID,
    actor: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
) -> None:
    client = db.get(OAuthClient, client_id)
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    block = db.get(ClientUserBlock, block_id)
    if block is None or block.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "封禁记录不存在")
    remove_block(db, block.id)
    log_audit(
        db,
        "admin",
        str(actor.id),
        "block_remove",
        category="admin_block",
        target_type="oauth_client",
        target_id=str(client.id),
    )
