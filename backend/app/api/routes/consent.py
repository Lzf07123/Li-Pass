from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_current_user
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.models.user_consent import UserConsent
from app.services.blocks import find_block
from app.services.oidc import (
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
)
from app.services.audit import log_audit
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
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    if pending.user_id and pending.user_id != str(user.id):
        # 待授权请求绑定发起用户：他人会话不得批准/拒绝，防串号授权。
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该授权请求不属于当前账号")
    client = db.scalar(
        select(OAuthClient).where(
            OAuthClient.client_id == pending.client_id, OAuthClient.is_active.is_(True)
        )
    )
    if client is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "应用不存在或已停用")
    if find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")

    session = get_current_session(request, db)
    code = create_authorization_code(
        db,
        user,
        client,
        pending.redirect_uri,
        pending.scope,
        pending.nonce,
        pending.code_challenge,
        pending.code_challenge_method,
        session.auth_method,
        session.id,
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
    log_audit(
        db,
        "user",
        str(user.id),
        "consent_approve",
        category="consent",
        target_type="oauth_client",
        target_id=str(client.id),
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"client_id": client.client_id, "scopes": granted},
    )
    store.delete(request_id)
    return {"redirect_url": build_authorize_redirect(pending.redirect_uri, code, pending.state)}


@router.post("/{request_id}/deny")
def deny(
    request_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    store = get_pending_request_store()
    pending = _get_pending_or_404(request_id)
    if pending.user_id and pending.user_id != str(user.id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该授权请求不属于当前账号")
    log_audit(
        db,
        "user",
        str(user.id),
        "consent_deny",
        category="consent",
        detail={"client_id": pending.client_id},
    )
    store.delete(request_id)
    return {"redirect_url": redirect_error(pending.redirect_uri, "access_denied", pending.state)}
