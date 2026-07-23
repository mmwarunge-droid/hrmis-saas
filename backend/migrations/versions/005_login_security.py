"""add persistent login lockout state

Revision ID: 005_login_security
Revises: 004_auth_sessions
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = '005_login_security'
down_revision = '004_auth_sessions'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default=sa.text('0')),
    )
    op.add_column('users', sa.Column('last_failed_login_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_users_locked_until', 'users', ['locked_until'])


def downgrade():
    op.drop_index('ix_users_locked_until', table_name='users')
    op.drop_column('users', 'locked_until')
    op.drop_column('users', 'last_failed_login_at')
    op.drop_column('users', 'failed_login_attempts')
