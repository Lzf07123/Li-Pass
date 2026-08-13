"""通知占位符渲染：按收件人替换 {nickname} / {email}。"""

from app.models.user import User


def render_template(template: str, user: User) -> str:
    return (
        template.replace("{nickname}", user.nickname or "")
        .replace("{email}", user.email)
    )
