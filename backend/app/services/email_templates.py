"""Li&Pass 品牌风 HTML 邮件模板。

依据 design-system/lipass/BRAND.md 的品牌令牌（安全蓝、石板灰、
克制排版与 Z 形品牌暗线）生成五类邮件的 HTML 版本。所有动态内容
一律 HTML 转义，正文通过 white-space:pre-line 保留换行。
"""

import html
from importlib.resources import files as resource_files

LOGO_BYTES = resource_files("app").joinpath("assets/email-logo.png").read_bytes()

_STYLE = """
  body { margin:0; padding:24px 12px; background-color:#F8FAFC;
    font-family:Inter,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,
    "Noto Sans","PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif;
    -webkit-font-smoothing:antialiased; }
  @media (prefers-color-scheme: dark) {
    .card { background-color:#111A2C !important; border-color:#263449 !important; }
    .fg { color:#E2E8F0 !important; }
    .body { color:#CBD5E1 !important; }
    .muted { color:#94A3B8 !important; }
    .primary { color:#38BDF8 !important; }
    .code { background-color:#082F49 !important; border-color:#164E63 !important;
      color:#38BDF8 !important; }
    .btn { background-color:#38BDF8 !important; color:#082F49 !important; }
    .footer { border-top-color:#263449 !important; }
  }
"""

_SHELL = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{style}</style>
</head>
<body>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    <td align="center">
      <table role="presentation" class="card" width="600" cellpadding="0"
        cellspacing="0" border="0"
        style="width:600px;max-width:100%;background-color:#FFFFFF;
          border:1px solid #E2E8F0;border-radius:16px;overflow:hidden;">
        <tr>
          <td style="padding:26px 32px 18px;">
            <table role="presentation" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td width="52" style="width:52px;">
                  <img src="cid:brand-logo" alt="Li&amp;Pass" width="40"
                    height="40" style="display:block;width:40px;height:40px;border:0;">
                </td>
                <td class="fg" style="font-size:15px;font-weight:600;
                  color:#0F172A;letter-spacing:0.01em;">Li&amp;Pass</td>
              </tr>
            </table>
            <div style="height:3px;margin-top:18px;line-height:0;">
              <svg viewBox="0 0 72 3" width="72" height="3" fill="none"
                aria-hidden="true" style="display:block;">
                <path d="M0 1h18l6-1 6 1h18l6 1 6-1h12"
                  stroke="#0369A1" stroke-opacity="0.35" stroke-width="1"/>
              </svg>
            </div>
          </td>
        </tr>
        <tr>
          <td style="padding:8px 32px 32px;">
            <h1 class="fg" style="margin:16px 0 12px;font-size:18px;
              line-height:1.35;font-weight:600;color:#0F172A;">{title}</h1>
            {body}
          </td>
        </tr>
        <tr>
          <td class="footer" style="border-top:1px solid #E2E8F0;
            padding:20px 32px 24px;font-size:12px;line-height:1.7;color:#64748B;">
            {footer}
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
</body>
</html>
"""

_FOOTER_SYSTEM = "此邮件由系统自动发送，请勿直接回复。"


def _shell(title: str, body: str, footer: str) -> str:
    return _SHELL.format(
        style=_STYLE,
        title=html.escape(title),
        body=body,
        footer=footer,
    )


def _code(code: str) -> str:
    return (
        '<span class="code" style="display:inline-block;margin:8px 0 4px;'
        "padding:12px 28px;background-color:#E0F2FE;"
        "border:1px solid #BAE6FD;border-radius:8px;color:#0369A1;"
        "font-size:26px;font-weight:600;letter-spacing:8px;"
        f'font-variant-numeric:tabular-nums;">{html.escape(code)}</span>'
    )


def _button(link: str, label: str) -> str:
    href = html.escape(link, quote=True)
    return (
        f'<a class="btn" href="{href}" style="display:inline-block;'
        "margin:8px 0 4px;padding:12px 28px;background-color:#0369A1;"
        "color:#FFFFFF;border-radius:8px;font-size:14px;font-weight:600;"
        f'text-decoration:none;">{html.escape(label)}</a>'
        '<p class="muted" style="margin:12px 0 0;font-size:12px;'
        "color:#64748B;word-break:break-all;\">如果按钮无法点击，"
        f'请复制以下链接到浏览器打开：<br><a class="primary" href="{href}" '
        f'style="color:#0369A1;text-decoration:underline;">{href}</a></p>'
    )


def render_verification(code: str) -> str:
    return _shell(
        "验证你的邮箱",
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;\">你正在验证邮箱地址。"
        "请输入以下验证码完成验证：</p>"
        + _code(code)
        + '<p class="muted" style="margin:16px 0 0;font-size:12px;'
        'line-height:1.6;color:#64748B;">验证码 10 分钟内有效。'
        "如果不是你本人操作，请忽略此邮件。</p>",
        _FOOTER_SYSTEM,
    )


def render_password_reset(code: str) -> str:
    return _shell(
        "重置密码",
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;\">我们收到你的密码重置请求。"
        "请输入以下验证码继续：</p>"
        + _code(code)
        + '<p class="muted" style="margin:16px 0 0;font-size:12px;'
        'line-height:1.6;color:#64748B;">验证码 10 分钟内有效。'
        "如果不是你本人操作，请忽略此邮件，你的密码不会被修改。</p>",
        _FOOTER_SYSTEM,
    )


def render_invite(link: str) -> str:
    return _shell(
        "你被邀请加入 Li&Pass",
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;\">你好，你被邀请注册 Li&amp;Pass 账号，"
        "一次注册即可通行所有授权网站。点击下方按钮完成注册（7 天内有效）：</p>"
        + _button(link, "完成注册"),
        _FOOTER_SYSTEM,
    )


def render_account_deleted(email: str, nickname: str | None) -> str:
    greeting = html.escape(f"您好，{nickname}：" if nickname else "您好：")
    return _shell(
        "你的账号已被删除",
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;\">" + greeting + "</p>"
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;\">你的 Li&amp;Pass 账号"
        f"（{html.escape(email)}）已被删除，将无法再登录相关网站。</p>"
        '<p class="muted" style="margin:16px 0 0;font-size:12px;'
        "line-height:1.6;color:#64748B;\">如非本人操作或对此有疑问，"
        "请联系平台管理员。</p>",
        _FOOTER_SYSTEM,
    )


def render_custom_notification(title: str, body_text: str, base_url: str) -> str:
    footer = (
        '不想再收到邮件通知？<a class="primary" href="'
        f'{html.escape(base_url.rstrip("/"), quote=True)}" '
        'style="color:#0369A1;text-decoration:none;">前往用户中心关闭</a><br>'
        + _FOOTER_SYSTEM
    )
    return _shell(
        title,
        '<p class="body" style="margin:0 0 12px;font-size:14px;'
        "line-height:1.7;color:#334155;white-space:pre-line;\">"
        + html.escape(body_text)
        + "</p>",
        footer,
    )
