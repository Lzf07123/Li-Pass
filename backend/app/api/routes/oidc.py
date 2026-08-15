import uuid
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

import jwt as pyjwt
from fastapi import APIRouter, Depends, Form, Header, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_session, get_optional_user
from app.core.config import get_settings
from app.core.db import get_db
from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.user import User, UserStatus
from app.models.user_consent import UserConsent
from app.security.jwt import (
    absolute_avatar_url,
    create_access_token,
    create_id_token,
    decode_token,
    public_jwks,
    userinfo_audience,
)
from app.security.tokens import hash_token
from app.services.blocks import find_block
from app.services.audit import log_audit
from app.services.oidc import (
    _as_utc,
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
    verify_pkce,
)
from app.services.pending_requests import PendingAuthRequest, get_pending_request_store

router = APIRouter(tags=["oidc"])


@router.get("/oauth2/authorize")
def authorize(
    request: Request,
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    response_type: str = Query(...),
    scope: str | None = Query(None),
    state: str | None = Query(None),
    nonce: str | None = Query(None),
    code_challenge: str | None = Query(None),
    code_challenge_method: str = Query("S256"),
    db: Session = Depends(get_db),
):
    frontend = get_settings().frontend_base_url
    if response_type != "code":
        return RedirectResponse(
            f"{frontend}/?error=unsupported_response_type", status_code=302
        )

    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        return RedirectResponse(
            f"{frontend}/?error=unauthorized_client", status_code=302
        )
    if redirect_uri not in client.redirect_uris:
        return RedirectResponse(
            f"{frontend}/?error=invalid_redirect_uri", status_code=302
        )

    requested = scope.split() if scope else list(client.scopes)
    if "openid" not in requested or not set(requested).issubset(set(client.scopes)):
        return RedirectResponse(
            redirect_error(redirect_uri, "invalid_scope", state), status_code=302
        )
    if not code_challenge or code_challenge_method != "S256":
        return RedirectResponse(
            redirect_error(redirect_uri, "invalid_request", state), status_code=302
        )

    user = get_optional_user(request, db)
    if user is None:
        settings = get_settings()
        next_url = f"{settings.jwt_issuer}/oauth2/authorize?{request.url.query}"
        login_url = f"{settings.frontend_base_url}/login?next={quote(next_url, safe='')}"
        return RedirectResponse(login_url, status_code=302)
    if find_block(db, client.id, user) is not None:
        return RedirectResponse(
            redirect_error(
                redirect_uri,
                "access_denied",
                state,
                "account_blocked",
            ),
            status_code=302,
        )
    if "email" in requested and user.email_verified_at is None:
        settings = get_settings()
        verify_url = (
            f"{settings.frontend_base_url}/verify-email?email={quote(user.email, safe='')}"
        )
        return RedirectResponse(verify_url, status_code=302)

    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    scope_ok = consent is not None and set(requested).issubset(set(consent.scopes))
    if scope_ok and not client.require_consent_every_time:
        session = get_current_session(request, db)
        code = create_authorization_code(
            db,
            user,
            client,
            redirect_uri,
            " ".join(requested),
            nonce,
            code_challenge,
            code_challenge_method,
            session.auth_method,
            session.id,
        )
        log_audit(
            db,
            "user",
            str(user.id),
            "oauth_authorize",
            category="oidc",
            target_type="oauth_client",
            target_id=str(client.id),
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            detail={"client_id": client.client_id, "scopes": requested},
        )
        return RedirectResponse(
            build_authorize_redirect(redirect_uri, code, state), status_code=302
        )

    pending = PendingAuthRequest(
        client_id=client.client_id,
        redirect_uri=redirect_uri,
        scope=" ".join(requested),
        state=state,
        nonce=nonce,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )
    request_id = get_pending_request_store().create(pending)
    return RedirectResponse(
        f"{frontend}/consent?request_id={request_id}", status_code=302
    )


@router.get("/.well-known/openid-configuration")
def discovery() -> dict:
    settings = get_settings()
    base = settings.jwt_issuer
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth2/authorize",
        "token_endpoint": f"{base}/oauth2/token",
        "userinfo_endpoint": f"{base}/oauth2/userinfo",
        "jwks_uri": f"{base}/oauth2/jwks",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email"],
        "code_challenge_methods_supported": ["S256"],
    }


@router.get("/oauth2/jwks")
def jwks() -> dict:
    return public_jwks()


@router.post("/oauth2/token")
def token(
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    if grant_type != "authorization_code":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unsupported_grant_type")
    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_client")
    if client.client_secret_hash is not None:
        if not client_secret or not secrets.compare_digest(
            hash_token(client_secret), client.client_secret_hash
        ):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_client")

    record = db.scalar(
        select(AuthorizationCode).where(
            AuthorizationCode.code_hash == hash_token(code or "")
        )
    )
    now = datetime.now(timezone.utc)
    if (
        record is None
        or record.client_id != client.id
        or record.redirect_uri != redirect_uri
        or record.consumed_at is not None
        or _as_utc(record.expires_at) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    if (
        client.client_secret_hash is None
        and not verify_pkce(code_verifier or "", record.code_challenge)
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")

    # 原子条件更新：并发请求只有一次能成功消费，消除 TOCTOU 竞态。
    consumed = db.execute(
        update(AuthorizationCode)
        .where(
            AuthorizationCode.id == record.id,
            AuthorizationCode.consumed_at.is_(None),
        )
        .values(consumed_at=now)
    )
    db.commit()
    if consumed.rowcount != 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    user = db.get(User, record.user_id)
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid_grant")
    if find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")

    if record.session_id is not None:
        link = db.scalar(
            select(OIDCClientSession).where(
                OIDCClientSession.session_id == record.session_id,
                OIDCClientSession.client_id == client.id,
            )
        )
        if link is None:
            db.add(
                OIDCClientSession(
                    session_id=record.session_id,
                    client_id=client.id,
                    user_id=user.id,
                )
            )
            db.commit()

    settings = get_settings()
    return {
        "access_token": create_access_token(user, client.client_id, record.scope),
        "token_type": "Bearer",
        "expires_in": settings.oauth_access_token_ttl_minutes * 60,
        "id_token": create_id_token(
            user,
            client.client_id,
            record.nonce,
            record.scope,
            "urn:portal-oss:acr:2fa"
            if record.auth_method in ("email_otp", "totp", "recovery")
            else "urn:portal-oss:acr:1fa",
            sid=str(record.session_id) if record.session_id else None,
        ),
    }


@router.get("/oauth2/userinfo")
def userinfo(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    try:
        claims = decode_token(
            authorization.removeprefix("Bearer "),
            audience=userinfo_audience(get_settings()),
        )
    except pyjwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    user = db.get(User, uuid.UUID(claims["sub"]))
    if user is None or user.status != UserStatus.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    client = db.scalar(
        select(OAuthClient).where(OAuthClient.client_id == claims["client_id"])
    )
    if client is not None and find_block(db, client.id, user) is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "该账号已被此网站限制访问")
    scopes = set(claims.get("scope", "").split())
    data: dict = {"sub": str(user.id)}
    # 按授权 scope 裁剪 claims：仅授予 openid 的客户端拿不到 email/nickname。
    if "email" in scopes:
        data["email"] = user.email
        data["email_verified"] = user.email_verified_at is not None
    if "profile" in scopes:
        data["nickname"] = user.nickname
        data["name"] = user.nickname
        picture = absolute_avatar_url(get_settings(), user.avatar_url)
        if picture:
            data["picture"] = picture
    return data
