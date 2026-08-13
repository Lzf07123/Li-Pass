"""add notification recalled_at

Revision ID: 8b3c4d5e6f7a
Revises: 7c0f1a2b3c4d
Create Date: 2026-08-14 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "8b3c4d5e6f7a"
down_revision: Union[str, None] = "7c0f1a2b3c4d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("recalled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("notifications", "recalled_at")
