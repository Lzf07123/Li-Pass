"""add stepup_at to sessions

Revision ID: f1a2b3c4d5e6
Revises: 7f2a9d3c8e1b
Create Date: 2026-08-16 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "7f2a9d3c8e1b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 敏感操作 step-up 复核时刻：可空，无历史数据需要回填；
    # 时间戳按项目惯例使用 DateTime(timezone=True)。
    op.add_column(
        "sessions",
        sa.Column("stepup_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "stepup_at")
