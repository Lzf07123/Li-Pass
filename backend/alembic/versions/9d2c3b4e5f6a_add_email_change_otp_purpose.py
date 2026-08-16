"""add email change otp purpose

Revision ID: 9d2c3b4e5f6a
Revises: 6e7f8a9b0c1d
Create Date: 2026-08-16 19:00:00.000000
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d2c3b4e5f6a"
down_revision: Union[str, None] = "6e7f8a9b0c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL 原生枚举只增不删：新用途「更换邮箱」追加取值。
    op.execute("ALTER TYPE otppurpose ADD VALUE IF NOT EXISTS 'change_email'")


def downgrade() -> None:
    # PostgreSQL 不支持删除已使用的枚举值；回滚方向为 no-op，
    # 与历史迁移的枚举扩展处理一致。
    pass
