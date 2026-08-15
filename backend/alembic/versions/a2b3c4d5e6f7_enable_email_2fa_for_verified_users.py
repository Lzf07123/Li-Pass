"""enable email 2fa for verified users

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-16 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 强制 2FA 的数据迁移：所有已验证邮箱且当前没有任何 2FA 方案的用户，
    # 默认启用邮箱验证码（注册验证邮箱后的默认第一方案）。
    # 仅在「既无邮箱 2FA 又无 TOTP」时写，避免覆盖用户已关闭邮箱 2FA、改用 TOTP 的选择。
    op.execute(
        """
        UPDATE users
        SET email_otp_enabled = true
        WHERE email_verified_at IS NOT NULL
          AND email_otp_enabled = false
          AND totp_secret_encrypted IS NULL
        """
    )


def downgrade() -> None:
    # 无法恢复「用户此前是否手动关闭过邮箱 2FA」的历史意图，
    # 回滚方向不做有损猜测；需要回滚时用后续迁移显式处理。
    pass
