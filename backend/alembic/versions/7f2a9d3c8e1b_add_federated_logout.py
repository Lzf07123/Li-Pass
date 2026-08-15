"""add federated logout

Revision ID: 7f2a9d3c8e1b
Revises: 6d1f9c0b2e4a
Create Date: 2026-08-15 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f2a9d3c8e1b'
down_revision: Union[str, None] = '6d1f9c0b2e4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'oauth_clients',
        sa.Column(
            'post_logout_redirect_uris',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
    )
    op.add_column(
        'oauth_clients',
        sa.Column('backchannel_logout_uri', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'authorization_codes',
        sa.Column('session_id', sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        None,
        'authorization_codes',
        'sessions',
        ['session_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_table(
        'oidc_client_sessions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('client_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['client_id'], ['oauth_clients.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['session_id'], ['sessions.id'], ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'client_id'),
    )
    op.create_index(
        op.f('ix_oidc_client_sessions_client_id'),
        'oidc_client_sessions',
        ['client_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_oidc_client_sessions_session_id'),
        'oidc_client_sessions',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_oidc_client_sessions_user_id'),
        'oidc_client_sessions',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_oidc_client_sessions_user_id'),
        table_name='oidc_client_sessions',
    )
    op.drop_index(
        op.f('ix_oidc_client_sessions_session_id'),
        table_name='oidc_client_sessions',
    )
    op.drop_index(
        op.f('ix_oidc_client_sessions_client_id'),
        table_name='oidc_client_sessions',
    )
    op.drop_table('oidc_client_sessions')
    op.drop_constraint(None, 'authorization_codes', type_='foreignkey')
    op.drop_column('authorization_codes', 'session_id')
    op.drop_column('oauth_clients', 'backchannel_logout_uri')
    op.drop_column('oauth_clients', 'post_logout_redirect_uris')
