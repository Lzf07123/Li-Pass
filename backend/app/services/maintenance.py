from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.account_invite import AccountInvite
from app.models.audit_log import AuditLog
from app.models.authorization_code import AuthorizationCode
from app.models.notification_recipient import NotificationRecipient
from app.models.otp import Otp
from app.models.session import Session


def cleanup_expired_ephemeral_rows(db: Session) -> dict[str, int]:
    """清理超过保留期的过期 OTP、授权码、邀请、审计日志与已下线会话。

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
    audit_cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().audit_retention_days
    )
    audit_result = db.execute(
        delete(AuditLog).where(AuditLog.created_at < audit_cutoff)
    )
    session_cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().session_retention_days
    )
    session_result = db.execute(
        delete(Session).where(
            or_(
                # 已吊销（管理员强制下线/用户主动退出）且超过保留期。
                and_(
                    Session.revoked_at.is_not(None),
                    Session.revoked_at < session_cutoff,
                ),
                # 从未显式吊销、但早已过期或空闲超时的“僵尸”会话。
                Session.expires_at < session_cutoff,
            )
        )
    )
    notification_cutoff = datetime.now(timezone.utc) - timedelta(
        days=get_settings().notification_retention_days
    )
    notification_result = db.execute(
        delete(NotificationRecipient).where(
            NotificationRecipient.read_at.is_not(None),
            NotificationRecipient.read_at < notification_cutoff,
        )
    )
    db.commit()
    return {
        "otps": otp_result.rowcount or 0,
        "authorization_codes": code_result.rowcount or 0,
        "account_invites": invite_result.rowcount or 0,
        "audit_logs": audit_result.rowcount or 0,
        "sessions": session_result.rowcount or 0,
        "notification_recipients": notification_result.rowcount or 0,
    }
