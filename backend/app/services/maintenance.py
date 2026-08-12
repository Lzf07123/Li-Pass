from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.account_invite import AccountInvite
from app.models.authorization_code import AuthorizationCode
from app.models.otp import Otp


def cleanup_expired_ephemeral_rows(db: Session) -> dict[str, int]:
    """清理超过保留期的过期 OTP、授权码与邀请，防止短期凭证表无限增长。

    只删除 expires_at 早于保留期的行（默认 7 天），这些行对业务已无意义，
    保留窗口仅用于近期排查。返回各表删除数量供日志与测试使用。
    """
    retention = timedelta(hours=get_settings().ephemeral_retention_hours)
    cutoff = datetime.now(timezone.utc) - retention
    otp_result = db.execute(delete(Otp).where(Otp.expires_at < cutoff))
    code_result = db.execute(
        delete(AuthorizationCode).where(AuthorizationCode.expires_at < cutoff)
    )
    invite_result = db.execute(
        delete(AccountInvite).where(AccountInvite.expires_at < cutoff)
    )
    db.commit()
    return {
        "otps": otp_result.rowcount or 0,
        "authorization_codes": code_result.rowcount or 0,
        "account_invites": invite_result.rowcount or 0,
    }
