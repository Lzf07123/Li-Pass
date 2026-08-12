"""add performance indexes

Revision ID: 9f3e2a1c4b5d
Revises: 87b77b1722e9
Create Date: 2026-08-13 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f3e2a1c4b5d"
down_revision: Union[str, None] = "87b77b1722e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 管理后台审计日志按时间倒序分页
    op.create_index(
        op.f("ix_audit_logs_created_at"),
        "audit_logs",
        ["created_at"],
        unique=False,
    )
    # OTP 校验按 purpose+target 精确查找后按创建时间取最新
    op.create_index(
        op.f("ix_otps_purpose_target_created_at"),
        "otps",
        ["purpose", "target", "created_at"],
        unique=False,
    )
    # 会话列表/批量吊销按 user_id + 未吊销过滤
    op.create_index(
        op.f("ix_sessions_user_id_revoked_at"),
        "sessions",
        ["user_id", "revoked_at"],
        unique=False,
    )
    # 黑名单按 client 查询：find_block 的 user 分支与 email 分支
    op.create_index(
        op.f("ix_client_user_blocks_client_id_user_id"),
        "client_user_blocks",
        ["client_id", "user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_user_blocks_client_id_email"),
        "client_user_blocks",
        ["client_id", "email"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_client_user_blocks_client_id_email"),
        table_name="client_user_blocks",
    )
    op.drop_index(
        op.f("ix_client_user_blocks_client_id_user_id"),
        table_name="client_user_blocks",
    )
    op.drop_index(
        op.f("ix_sessions_user_id_revoked_at"),
        table_name="sessions",
    )
    op.drop_index(
        op.f("ix_otps_purpose_target_created_at"),
        table_name="otps",
    )
    op.drop_index(
        op.f("ix_audit_logs_created_at"),
        table_name="audit_logs",
    )
