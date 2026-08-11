from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user
from app.core.db import get_db
from app.models.oauth_client import OAuthClient
from app.models.user_consent import UserConsent
from app.services.oidc import (
    build_authorize_redirect,
    create_authorization_code,
    redirect_error,
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
    if response_type != "code":
        return RedirectResponse("/?error=unsupported_response_type", status_code=302)

    client = db.scalar(select(OAuthClient).where(OAuthClient.client_id == client_id))
    if client is None or not client.is_active:
        return RedirectResponse("/?error=unauthorized_client", status_code=302)
    if redirect_uri not in client.redirect_uris:
        return RedirectResponse("/?error=invalid_redirect_uri", status_code=302)

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
        next_url = f"/oauth2/authorize?{request.url.query}"
        return RedirectResponse(f"/login?next={quote(next_url, safe='')}", status_code=302)

    consent = db.scalar(
        select(UserConsent).where(
            UserConsent.user_id == user.id, UserConsent.client_id == client.id
        )
    )
    scope_ok = consent is not None and set(requested).issubset(set(consent.scopes))
    if scope_ok and not client.require_consent_every_time:
        code = create_authorization_code(
            db,
            user,
            client,
            redirect_uri,
            " ".join(requested),
            nonce,
            code_challenge,
            code_challenge_method,
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
    return RedirectResponse(f"/consent?request_id={request_id}", status_code=302)
