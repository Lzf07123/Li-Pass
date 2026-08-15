import base64
import hashlib
import os
import secrets
from urllib.parse import urlencode

import requests
import jwt as pyjwt
from flask import Flask, redirect, render_template_string, request, session

ISSUER = os.environ["PORTAL_ISSUER"]
API_BASE = os.environ.get("PORTAL_API_BASE", ISSUER)
CLIENT_ID = os.environ["PORTAL_CLIENT_ID"]
REDIRECT_URI = os.environ["DEMO_REDIRECT_URI"]
DEMO_PATH_PREFIX = os.environ.get("DEMO_PATH_PREFIX", "").rstrip("/")
DEMO_HOME_URL = os.environ.get("DEMO_HOME_URL", "")

app = Flask(__name__)
app.secret_key = os.environ.get("DEMO_SECRET_KEY") or secrets.token_urlsafe(32)

AUTHORIZE_URL = f"{ISSUER}/oauth2/authorize"
TOKEN_URL = f"{API_BASE}/oauth2/token"
USERINFO_URL = f"{API_BASE}/oauth2/userinfo"
END_SESSION_URL = f"{ISSUER}/oauth2/end-session"

INDEX_HTML = """
<!doctype html>
<html>
  <body style="font-family: sans-serif; max-width: 640px; margin: 40px auto">
    <h1>示例授权网站</h1>
    {% if user %}
      <p>已通过门户登录：</p>
      <ul>
        <li>邮箱：{{ user.email }}</li>
        <li>昵称：{{ user.nickname }}</li>
        <li>邮箱已验证：{{ user.email_verified }}</li>
      </ul>
      <p>退出方式（两种语义，演示用）：</p>
      <form method="post" action="{{ prefix }}/local-logout">
        <button type="submit">登出本网站</button>
      </form>
      <form method="post" action="{{ prefix }}/logout">
        <button type="submit">登出 SSO（退出所有网站）</button>
      </form>
    {% else %}
      <p><a href="{{ prefix }}/login">通过门户登录</a></p>
    {% endif %}
  </body>
</html>
"""


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@app.get("/")
def index():
    return render_template_string(
        INDEX_HTML, user=session.get("user"), prefix=DEMO_PATH_PREFIX
    )


@app.get("/login")
def login():
    verifier, challenge = pkce_pair()
    session["verifier"] = verifier
    session["state"] = secrets.token_urlsafe(24)
    session["nonce"] = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "openid profile email",
        "state": session["state"],
        "nonce": session["nonce"],
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")


@app.get("/callback")
def callback():
    error = request.args.get("error")
    if error:
        return f"授权失败: {error}", 400
    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state != session.get("state"):
        return "state 校验失败", 400
    response = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "code_verifier": session.get("verifier"),
        },
        timeout=10,
    )
    if response.status_code != 200:
        return f"换取令牌失败: {response.text}", 400
    token = response.json()
    try:
        # 密钥从后端内网地址拉取（浏览器侧 ISSUER 可能是宿主机 localhost）。
        jwks_client = pyjwt.PyJWKClient(f"{API_BASE}/oauth2/jwks")
        signing_key = jwks_client.get_signing_key_from_jwt(token["id_token"])
        claims = pyjwt.decode(
            token["id_token"],
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={"require": ["exp", "iat", "iss", "aud", "nonce"]},
        )
    except pyjwt.PyJWTError as exc:
        app.logger.warning("id_token 校验失败: %s", exc)
        return "id_token 校验失败", 400
    if claims.get("nonce") != session.get("nonce"):
        return "nonce 校验失败", 400
    user_response = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {token['access_token']}"},
        timeout=10,
    )
    if user_response.status_code != 200:
        return "获取用户信息失败", 400
    session["user"] = user_response.json()
    session["sid"] = claims.get("sid")
    return redirect(f"{DEMO_PATH_PREFIX}/")


@app.get("/logout")
def logout():
    """门户发起串跳漏斗：清本地会话后跳 next。"""
    session.clear()
    next_url = request.args.get("next") or f"{DEMO_PATH_PREFIX}/"
    if not next_url.startswith("/") or next_url.startswith("//"):
        next_url = f"{DEMO_PATH_PREFIX}/"
    return redirect(next_url)


@app.post("/local-logout")
def local_logout():
    """登出本网站：只清本地会话，不打扰门户 SSO 与其它授权网站。"""
    session.clear()
    return redirect(f"{DEMO_PATH_PREFIX}/")


@app.post("/logout")
def logout_initiate():
    """登出 SSO：清本地会话后引导用户到 IdP 统一退出全部网站。"""
    session.clear()
    post_logout_redirect_uri = DEMO_HOME_URL or f"{ISSUER}{DEMO_PATH_PREFIX}/"
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": CLIENT_ID,
        "post_logout_redirect_uri": post_logout_redirect_uri,
        "state": state,
    }
    return redirect(f"{END_SESSION_URL}?{urlencode(params)}")


@app.post("/backchannel-logout")
def backchannel_logout():
    """接收 IdP 的 logout_token（服务器间），校验后清本地会话。"""
    token = request.form.get("logout_token")
    if not token:
        return "缺少 logout_token", 400
    try:
        jwks_client = pyjwt.PyJWKClient(f"{API_BASE}/oauth2/jwks")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=CLIENT_ID,
            issuer=ISSUER,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", "sid", "events"]
            },
        )
    except pyjwt.PyJWTError as exc:
        app.logger.warning("登出令牌校验失败: %s", exc)
        return "登出令牌校验失败", 400
    if (
        "http://schemas.openid.net/event/backchannel-logout"
        not in claims.get("events", {})
    ):
        return "非登出事件令牌", 400
    # 演示站用浏览器 Cookie 承载会话，回程 POST 无 Cookie，故匹配不到时
    # 仅校验令牌不清理；生产接入方应按 docs/oidc-integration.md 用服务端
    # 会话存储按 (sub, sid) 定位并下线，同时维护 jti 已见缓存与新鲜窗口。
    if session.get("sid") == claims["sid"]:
        session.clear()
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3001)
