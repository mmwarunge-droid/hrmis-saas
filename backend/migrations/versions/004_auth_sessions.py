"""add persistent authentication sessions

Revision ID: 004_auth_sessions
Revises: 003_seed_default_roles
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '004_auth_sessions'
down_revision = '003_seed_default_roles'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.create_table(
        'auth_sessions',
        sa.Column('id', UUID, primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('refresh_jti_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_reason', sa.String(120), nullable=True),
        sa.Column('ip_address', sa.String(80), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('refresh_jti_hash', name='uq_auth_sessions_refresh_jti_hash'),
    )
    op.create_index('ix_auth_sessions_tenant_id', 'auth_sessions', ['tenant_id'])
    op.create_index('ix_auth_sessions_user_id', 'auth_sessions', ['user_id'])
    op.create_index('ix_auth_sessions_expires_at', 'auth_sessions', ['expires_at'])
    op.create_index('ix_auth_sessions_revoked_at', 'auth_sessions', ['revoked_at'])
    op.create_index(
        'ix_auth_sessions_user_active',
        'auth_sessions',
        ['user_id', 'revoked_at', 'expires_at'],
    )


def downgrade():
    op.drop_index('ix_auth_sessions_user_active', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_revoked_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_expires_at', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_user_id', table_name='auth_sessions')
    op.drop_index('ix_auth_sessions_tenant_id', table_name='auth_sessions')
    op.drop_table('auth_sessions')
