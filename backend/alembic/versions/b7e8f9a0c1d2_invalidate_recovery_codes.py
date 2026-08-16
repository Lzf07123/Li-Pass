"""invalidate recovery codes

Revision ID: b7e8f9a0c1d2
Revises: 9d2c3b4e5f6a
Create Date: 2026-08-16 23:20:00.000000

旧版恢复码以裸 SHA-256 存储（弱哈希），且新版本把恢复码 HMAC 密钥改为
从加密主密钥域分离派生，存量行无法与旧弱哈希行区分，统一作废并强制
用户重新生成（重新开启 TOTP 即可获得新恢复码）。
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7e8f9a0c1d2"
down_revision: Union[str, None] = "9d2c3b4e5f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM recovery_codes")


def downgrade() -> None:
    # 数据删除不可逆：回滚方向为 no-op（恢复码只能重新生成，无法恢复）。
    pass
