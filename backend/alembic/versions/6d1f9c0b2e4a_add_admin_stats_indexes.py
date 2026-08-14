"""add audit_logs (action, created_at) index for admin stats

Revision ID: 6d1f9c0b2e4a
Revises: 8b3c4d5e6f7a
Create Date: 2026-08-14 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d1f9c0b2e4a"
down_revision: Union[str, None] = "8b3c4d5e6f7a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 管理后台数据统计按 action ∈ (login, 2fa_login) + 时间窗口聚合，
    # 复合索引避免整表扫描。
    op.create_index(
        op.f("ix_audit_logs_action_created_at"),
        "audit_logs",
        ["action", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_audit_logs_action_created_at"),
        table_name="audit_logs",
    )
