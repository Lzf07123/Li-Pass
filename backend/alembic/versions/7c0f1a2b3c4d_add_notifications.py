"""add notifications

Revision ID: 7c0f1a2b3c4d
Revises: e3f5a7b9c1d2
Create Date: 2026-08-14 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c0f1a2b3c4d"
down_revision: Union[str, None] = "e3f5a7b9c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("in_site", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sender_id", sa.Uuid(), nullable=True),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("email_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "notification_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["notifications.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "notification_id", "user_id", name="uq_notification_recipient"
        ),
    )
    op.create_index(
        op.f("ix_notification_recipients_notification_id"),
        "notification_recipients",
        ["notification_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_recipients_user_id"),
        "notification_recipients",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_recipients_user_created",
        "notification_recipients",
        ["user_id", "created_at"],
        unique=False,
    )
    op.add_column(
        "users",
        sa.Column(
            "email_notifications",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "email_notifications")
    op.drop_index(
        "ix_notification_recipients_user_created",
        table_name="notification_recipients",
    )
    op.drop_index(
        op.f("ix_notification_recipients_user_id"),
        table_name="notification_recipients",
    )
    op.drop_index(
        op.f("ix_notification_recipients_notification_id"),
        table_name="notification_recipients",
    )
    op.drop_table("notification_recipients")
    op.drop_table("notifications")
