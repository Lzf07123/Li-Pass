from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent
from app.services.oidc import (
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
)
from app.services.pending_requests import get_pending_request_store

router = APIRouter(prefix="/api/v1/consent", tags=["consent"])


def _get_pending_or_404(request_id: str):
    pending = get_pending_request_store().get(request_id)
    if pending is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "授权请求不存在或已过期")
    return pending


@router.get("/{request_id}")
def consent_info(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    pending = _get_pending_or_404(request_id)
    client = db.scalar(
        select(OAuthClient).where(OAuthClient.client_id == pending.client_id)
    )
    if client is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "应用不存在")
    return {
        "request_id": request_id,
        "client": {
            "name": client.name,
            "logo_url": client.logo_url,
            "description": client.description,
        },
        "scopes": pending.scope.split(),
    }


@router.post("/{request_id}/approve")
def approve(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    client = db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == pending.client_id, OAuthClient.is_active.is_(True)
        )
    )
    if client is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "应用不存在或已停用")

    code = create_authorization_code(
        db,
        user,
        client,
        pending.redirect_uri,
        pending.scope,
        pending.nonce,
        pending.code_challenge,
        pending.code_challenge_method,
    )
    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    granted = pending.scope.split()
    if consent is None:
        db.add(UserConsent(user_id=user.id, client_id=client.id, scopes=granted))
    else:
        consent.scopes = sorted(set(consent.scopes) | set(granted))
    db.commit()
    store.delete(request_id)
    return {"redirect_url": build_authorize_redirect(pending.redirect_uri, code, pending.state)}


@router.post("/{request_id}/deny")
def deny(
    request_id: str,
    user: User = Depends(get_current_user),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    store.delete(request_id)
    return {"redirect_url": redirect_error(pending.redirect_uri, "access_denied", pending.state)}
