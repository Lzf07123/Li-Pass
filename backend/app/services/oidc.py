import base64
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.authorization_code import AuthorizationCode
from app.security.tokens import hash_token


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def redirect_error(
    redirect_uri: str,
    error: str,
    state: str | None = None,
    error_description: str | None = None,
) -> str:
    params = {"error": error}
    if state:
        params["state"] = state
    if error_description:
        params["error_description"] = error_description
    separator = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{separator}{urlencode(params)}"


def build_authorize_redirect(redirect_uri: str, code: str, state: str | None = None) -> str:
    params = {"code": code}
    if state:
        params["state"] = state
    separator = "&" if "?" in redirect_uri else "?"
    return f"{redirect_uri}{separator}{urlencode(params)}"


def verify_pkce(code_verifier: str, code_challenge: str | None) -> bool:
    if not code_challenge:
        return False
    # RFC 7636 §4.1：verifier 长度必须落在 43–128 字符窗口。
    if not 43 <= len(code_verifier) <= 128:
        return False
    digest = hashlib.sha256(code_verifier.encode()).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return secrets.compare_digest(expected, code_challenge)


def create_authorization_code(
    db: Session,
    user,
    client,
    redirect_uri: str,
    scope: str,
    nonce: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str = "S256",
    auth_method: str = "password",
    session_id: uuid.UUID | None = None,
) -> str:
    settings = get_settings()
    code = secrets.token_urlsafe(32)
    db.add(
        AuthorizationCode(
            code_hash=hash_token(code),
            client_id=client.id,
            user_id=user.id,
            redirect_uri=redirect_uri,
            scope=scope,
            nonce=nonce,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            auth_method=auth_method,
            session_id=session_id,
            expires_at=datetime.now(timezone.utc)
            + timedelta(minutes=settings.oauth_code_ttl_minutes),
        )
    )
    db.commit()
    return code
