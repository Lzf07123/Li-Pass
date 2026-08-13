"""add audit category

Revision ID: e3f5a7b9c1d2
Revises: 9f3e2a1c4b5d
Create Date: 2026-08-13 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e3f5a7b9c1d2"
down_revision: Union[str, None] = "c2a3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTION_CATEGORY = {
    "login": "auth",
    "login_step1": "auth",
    "2fa_login": "auth",
    "user_register_by_invite": "auth",
    "password_reset": "auth",
    "login_failed": "security",
    "2fa_login_failed": "security",
    "password_change": "user",
    "user_delete_self": "user",
    "app_consent_revoke": "consent",
    "2fa_email_enable": "2fa",
    "2fa_email_disable": "2fa",
    "2fa_totp_enable": "2fa",
    "2fa_totp_disable": "2fa",
    "admin_create_user": "admin_user",
    "admin_invite_user": "admin_user",
    "admin_cancel_invite": "admin_user",
    "admin_resend_invite": "admin_user",
    "admin_delete_invite": "admin_user",
    "admin_batch_invite_user": "admin_user",
    "admin_batch_update_user": "admin_user",
    "admin_update_user": "admin_user",
    "admin_reset_password": "admin_user",
    "admin_reset_2fa": "admin_user",
    "admin_batch_delete_user": "admin_user",
    "admin_delete_user": "admin_user",
    "admin_create_client": "admin_client",
    "admin_update_client": "admin_client",
    "admin_delete_client": "admin_client",
    "admin_reset_client_secret": "admin_client",
    "block_add": "admin_block",
    "block_remove": "admin_block",
    "admin_update_site_setting": "admin_settings",
}


def upgrade() -> None:
    op.add_column(
        "audit_logs",
        sa.Column("category", sa.String(length=30), nullable=True),
    )
    connection = op.get_bind()
    for action, category in ACTION_CATEGORY.items():
        connection.execute(
            sa.text(
                "UPDATE audit_logs SET category = :category "
                "WHERE action = :action AND category IS NULL"
            ),
            {"category": category, "action": action},
        )
    connection.execute(
        sa.text(
            "UPDATE audit_logs SET category = 'other' WHERE category IS NULL"
        )
    )
    op.create_index(
        op.f("ix_audit_logs_category"),
        "audit_logs",
        ["category"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_logs_category"), table_name="audit_logs")
    op.drop_column("audit_logs", "category")
