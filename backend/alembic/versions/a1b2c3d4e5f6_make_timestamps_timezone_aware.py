"""make timestamp columns timezone aware

Revision ID: a1b2c3d4e5f6
Revises: 0e217d240e66
Create Date: 2026-08-12 05:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "0e217d240e66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Upgrade naive timestamp columns to timezone-aware so aware/naive
    # comparisons (Task 3+ / get_current_user) work on PostgreSQL.
    op.alter_column("users", "email_verified_at", type_=sa.DateTime(timezone=True))
    op.alter_column("users", "phone_verified_at", type_=sa.DateTime(timezone=True))
    op.alter_column("users", "last_login_at", type_=sa.DateTime(timezone=True))
    op.alter_column("sessions", "expires_at", type_=sa.DateTime(timezone=True))
    op.alter_column("sessions", "revoked_at", type_=sa.DateTime(timezone=True))
    op.alter_column("otps", "expires_at", type_=sa.DateTime(timezone=True))
    op.alter_column("otps", "consumed_at", type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    op.alter_column("otps", "consumed_at", type_=sa.DateTime())
    op.alter_column("otps", "expires_at", type_=sa.DateTime())
    op.alter_column("sessions", "revoked_at", type_=sa.DateTime())
    op.alter_column("sessions", "expires_at", type_=sa.DateTime())
    op.alter_column("users", "last_login_at", type_=sa.DateTime())
    op.alter_column("users", "phone_verified_at", type_=sa.DateTime())
    op.alter_column("users", "email_verified_at", type_=sa.DateTime())
