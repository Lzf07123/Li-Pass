import uuid
import secrets
from datetime import datetime, timezone
from urllib.parse import quote

import jwt as pyjwt
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import (
    clear_session_cookie,
    get_current_session,
    get_optional_session,
    get_optional_user,
)
from app.core.config import get_settings
from app.core.db import get_db
from app.models.authorization_code import AuthorizationCode
from app.models.oauth_client import OAuthClient
from app.models.oidc_client_session import OIDCClientSession
from app.models.user import User, UserStatus
from app.models.user_consent import UserConsent
from app.security.jwt import (
    absolute_avatar_url,
    compute_at_hash,
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
from app.services.rate_limit import get_rate_limiter
from app.services.federated_logout import (
    collect_logout_targets,
    dispatch_backchannel_logout,
)
from app.services.logout_requests import (
    PendingLogoutRequest,
    get_logout_request_store,
)

router = APIRouter(tags=["oidc"])


def _oauth_error(
    status_code: int,
    error: str,
    error_description: str,
    www_authenticate: str | None = None,
) -> JSONResponse:
    """RFC 6749 §5.2 错误响应：token 端点使用标准 error/error_description 字段。"""
    headers = {"Cache-Control": "no-store"}
    if www_authenticate:
        headers["WWW-Authenticate"] = www_authenticate
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "error_description": error_description},
        headers=headers,
    )


@router.get("/oauth2/authorize")
def authorize(
    request: Request,
    client_id: str = Query(..., max_length=128),
    redirect_uri: str = Query(..., max_length=1000),
    response_type: str = Query(...),
    scope: str | None = Query(None, max_length=500),
    state: str | None = Query(None, max_length=512),
    nonce: str | None = Query(None, max_length=255),
    code_challenge: str | None = Query(None, max_length=255),
    code_challenge_method: str = Query("S256"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit(
            "authorize", ip, settings.authorize_rate_window_seconds
        )
        > settings.authorize_rate_limit
    ):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "请求过于频繁，请稍后再试"
        )
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
        next_url = f"{settings.jwt_issuer}/oauth2/authorize?{request.url.query}"
        verify_url = (
            f"{settings.frontend_base_url}/verify-email?email={quote(user.email, safe='')}"
            f"&next={quote(next_url, safe='')}"
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
        user_id=str(user.id),
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
        "token_endpoint_auth_methods_supported": [
            "none",
            "client_secret_post",
        ],
        "claims_supported": [
            "sub",
            "email",
            "email_verified",
            "nickname",
            "name",
            "picture",
            "acr",
            "sid",
        ],
        "end_session_endpoint": f"{base}/oauth2/end-session",
        "backchannel_logout_supported": True,
        "frontchannel_logout_supported": False,
    }


def _append_state(uri: str | None, state: str | None) -> str | None:
    if not uri:
        return uri
    if not state:
        return uri
    separator = "&" if "?" in uri else "?"
    return f"{uri}{separator}state={quote(state, safe='')}"


def _resolve_logout_client(
    db: Session, client_id: str | None, id_token_hint: str | None
) -> OAuthClient | None:
    if client_id:
        return db.scalar(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active.is_(True),
            )
        )
    if id_token_hint:
        try:
            claims = decode_token(id_token_hint)
        except pyjwt.PyJWTError:
            return None
        audience = claims.get("aud")
        if isinstance(audience, str):
            return db.scalar(
                select(OAuthClient).where(
                    OAuthClient.client_id == audience,
                    OAuthClient.is_active.is_(True),
                )
            )
    return None


@router.get("/oauth2/end-session")
def end_session(
    request: Request,
    id_token_hint: str | None = Query(None),
    post_logout_redirect_uri: str | None = Query(None),
    state: str | None = Query(None),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """OIDC RP-Initiated Logout：校验回跳白名单后进入确认页。"""
    frontend = get_settings().frontend_base_url
    client = _resolve_logout_client(db, client_id, id_token_hint)
    if post_logout_redirect_uri and (
        client is None
        or post_logout_redirect_uri not in client.post_logout_redirect_uris
    ):
        return RedirectResponse(
            f"{frontend}/?error=invalid_logout_redirect", status_code=302
        )
    target = _append_state(post_logout_redirect_uri, state) or f"{frontend}/"
    session = get_optional_session(request, db)
    if session is None:
        # 规范要求：即便 IdP 没有会话，也应正常回跳而不是报错。
        return RedirectResponse(target, status_code=302)
    pending = PendingLogoutRequest(
        client_id=client.client_id if client else "",
        post_logout_redirect_uri=post_logout_redirect_uri,
        state=state,
        sid=str(session.id),
        sub=str(session.user_id),
        client_name=client.name if client else "",
    )
    request_id = get_logout_request_store().create(pending)
    return RedirectResponse(
        f"{frontend}/logout/confirm?request_id={request_id}", status_code=302
    )


def _get_pending_logout_or_404(request_id: str) -> PendingLogoutRequest:
    pending = get_logout_request_store().get(request_id)
    if pending is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "登出请求不存在或已过期"
        )
    return pending


@router.get("/api/v1/oauth/logout-requests/{request_id}")
def logout_request_info(request_id: str) -> dict:
    """确认页展示用；公开只读，避免会话已失效时页面无法回跳。"""
    pending = _get_pending_logout_or_404(request_id)
    return {"client_name": pending.client_name}


@router.post("/api/v1/oauth/logout-requests/{request_id}/confirm")
def confirm_logout_request(
    request_id: str,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    session = get_current_session(request, db)
    pending = _get_pending_logout_or_404(request_id)
    settings = get_settings()
    session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    targets = collect_logout_targets(db, [session.id])
    if targets:
        background_tasks.add_task(dispatch_backchannel_logout, targets)
    log_audit(
        db,
        "user",
        str(session.user_id),
        "oidc_end_session",
        category="oidc",
        target_type="oauth_client",
        target_id=pending.client_id or None,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        detail={"sid": pending.sid, "backchannel_targets": len(targets)},
    )
    get_logout_request_store().delete(request_id)
    clear_session_cookie(response)
    return {
        "redirect_url": _append_state(
            pending.post_logout_redirect_uri, pending.state
        )
        or f"{settings.frontend_base_url}/"
    }


@router.post("/api/v1/oauth/logout-requests/{request_id}/local-only")
def local_only_logout_request(
    request_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """仅登出本网站：保留门户会话，删除待确认请求并回跳发起方。"""
    pending = _get_pending_logout_or_404(request_id)
    get_logout_request_store().delete(request_id)
    return {
        "redirect_url": _append_state(
            pending.post_logout_redirect_uri, pending.state
        )
        or f"{get_settings().frontend_base_url}/"
    }


@router.get("/oauth2/jwks")
def jwks() -> dict:
    return public_jwks()


@router.post("/oauth2/token")
def token(
    request: Request,
    grant_type: str = Form(...),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    client_id: str = Form(...),
    client_secret: str | None = Form(None),
    code_verifier: str | None = Form(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    ip = request.client.host if request.client else ""
    if (
        get_rate_limiter().hit("token", ip, settings.token_rate_window_seconds)
        > settings.token_rate_limit
    ):
        return _oauth_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "rate_limited",
            "请求过于频繁，请稍后再试",
        )
    if grant_type != "authorization_code":
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST,
            "unsupported_grant_type",
            "不支持的授权类型",
        )
    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST, "invalid_client", "客户端不存在或已停用"
        )
    if client.client_secret_hash is not None:
        if not client_secret or not secrets.compare_digest(
            hash_token(client_secret), client.client_secret_hash
        ):
            return _oauth_error(
                status.HTTP_401_UNAUTHORIZED,
                "invalid_client",
                "客户端凭据错误",
                www_authenticate="Basic",
            )

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
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST, "invalid_grant", "授权码无效、过期或已被使用"
        )
    # OAuth 2.1：PKCE 对所有客户端（含机密客户端）强制。
    if not verify_pkce(code_verifier or "", record.code_challenge):
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST, "invalid_grant", "PKCE 校验失败"
        )

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
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST, "invalid_grant", "授权码已被使用"
        )
    user = db.get(User, record.user_id)
    if user is None or user.status != UserStatus.active:
        return _oauth_error(
            status.HTTP_400_BAD_REQUEST, "invalid_grant", "授权码无效"
        )
    if find_block(db, client.id, user) is not None:
        return _oauth_error(
            status.HTTP_403_FORBIDDEN,
            "access_denied",
            "该账号已被此网站限制访问",
        )

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
            try:
                db.commit()
            except IntegrityError:
                # 同一 (session, client) 并发换码时可能同时插入：唯一约束
                # 兜底，回滚后继续发令牌，不影响本次授权。
                db.rollback()
        elif link.revoked_at is not None:
            # 重新授权：激活此前因会话下线而吊销的登录链接。
            link.revoked_at = None
            db.commit()

    settings = get_settings()
    access_token = create_access_token(
        user, client.client_id, record.scope
    )
    return {
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": settings.oauth_access_token_ttl_minutes * 60,
        "id_token": create_id_token(
            user,
            client.client_id,
            record.nonce,
            record.scope,
            "urn:lipass:acr:2fa"
            if record.auth_method in ("email_otp", "totp", "recovery")
            else "urn:lipass:acr:1fa",
            sid=str(record.session_id) if record.session_id else None,
            at_hash=compute_at_hash(access_token),
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
