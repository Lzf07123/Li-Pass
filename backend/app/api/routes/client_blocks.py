import base64
import secrets
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.client_user_block import ClientUserBlock
from app.models.oauth_client import OAuthClient
from app.schemas.oauth import ClientBlockCreate
from app.security.tokens import hash_token
from app.services.blocks import add_block, list_blocks, remove_block
from app.services.audit import log_audit

router = APIRouter(prefix="/oauth2/client", tags=["client-blocks"])


def _auth_client(authorization: str, db: Session) -> OAuthClient:
    if not authorization or not authorization.startswith("Basic "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    try:
        raw = base64.b64decode(authorization.removeprefix("Basic ")).decode()
        client_id, client_secret = raw.split(":", 1)
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or client.client_secret_hash is None or not client.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    if not secrets.compare_digest(hash_token(client_secret), client.client_secret_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")
    return client


def _serialize(block) -> dict:
    return {
        "id": str(block.id),
        "user_id": str(block.user_id) if block.user_id else None,
        "email": block.email,
        "reason": block.reason,
        "created_at": block.created_at,
    }


@router.get("/blocks", response_model=list[dict])
def list_client_blocks(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> list[dict]:
    client = _auth_client(authorization or "", db)
    return [_serialize(b) for b in list_blocks(db, client.id)]


@router.post("/blocks", response_model=dict)
def create_client_block(
    payload: ClientBlockCreate,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    client = _auth_client(authorization or "", db)
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
        "client",
        client.client_id,
        "block_add",
        category="admin_block",
        detail={"email": block.email, "user_id": str(block.user_id) if block.user_id else None},
    )
    return _serialize(block)


@router.delete("/blocks/{block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_block(
    block_id: uuid.UUID,
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> None:
    client = _auth_client(authorization or "", db)
    block = db.get(ClientUserBlock, block_id)
    if block is None or block.client_id != client.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "封禁记录不存在")
    remove_block(db, block.id)
    log_audit(
        db,
        "client",
        client.client_id,
        "block_remove",
        category="admin_block",
    )
