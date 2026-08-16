from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy import delete, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.admin_stats import invalidate_admin_stats_cache
from app.models.account_invite import AccountInvite
from app.models.authorization_code import AuthorizationCode
from app.models.client_user_block import ClientUserBlock
from app.models.otp import Otp
from app.models.recovery_code import RecoveryCode
from app.models.session import Session as SessionModel
from app.models.user import User
from app.models.user_consent import UserConsent
from app.services.avatar_cleanup import delete_avatar_file


def delete_user_account(db: Session, user: User, *, commit: bool = True) -> None:
    """永久删除用户及其全部关联数据（不含审计日志，审计记录保留以便追溯）。

    显式删除而非依赖数据库外键级联：PostgreSQL 开启外键时行为一致，
    SQLite 测试环境默认不开启外键级联，显式删除保证两条路径结果相同。
    """
    db.execute(delete(SessionModel).where(SessionModel.user_id == user.id))
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id))
    db.execute(delete(UserConsent).where(UserConsent.user_id == user.id))
    db.execute(delete(AuthorizationCode).where(AuthorizationCode.user_id == user.id))
    db.execute(delete(ClientUserBlock).where(ClientUserBlock.user_id == user.id))
    # OTP 以邮箱为目标存储：删除该邮箱的未消费验证码，
    # 防止旧验证码在邮箱重新注册后仍可被使用。
    db.execute(delete(Otp).where(Otp.target == user.email))

    # 邀请注册的账号被删除后，把已消费的邀请标记为“已取消”，原链接立即失效；
    # 同时避免残留一条“待注册”记录阻塞管理员对该邮箱重新发起邀请。
    db.execute(
        update(AccountInvite)
        .where(
            AccountInvite.email == user.email,
            AccountInvite.used_at.is_not(None),
            AccountInvite.cancelled_at.is_(None),
        )
        .values(cancelled_at=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )

    # 删除本地上传的头像文件并清理用户专属目录。
    upload_dir = Path(get_settings().avatar_upload_dir).resolve()
    owner_dir = upload_dir / str(user.id)
    if owner_dir.is_dir():
        delete_avatar_file(upload_dir, user.avatar_url, owner_dir=owner_dir)
        try:
            owner_dir.rmdir()
        except OSError:
            pass

    db.delete(user)
    if commit:
        db.commit()
    invalidate_admin_stats_cache()
