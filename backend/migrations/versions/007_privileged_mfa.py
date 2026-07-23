"""add privileged role multi-factor authentication

Revision ID: 007_privileged_mfa
Revises: 006_account_recovery
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '007_privileged_mfa'
down_revision = '006_account_recovery'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column('users', sa.Column('mfa_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mfa_pending_secret_encrypted', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('mfa_enabled_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('mfa_last_used_timecode', sa.BigInteger(), nullable=True))
    op.create_index('ix_users_mfa_enabled_at', 'users', ['mfa_enabled_at'])

    op.add_column('auth_sessions', sa.Column('mfa_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_auth_sessions_mfa_verified_at', 'auth_sessions', ['mfa_verified_at'])

    op.create_table(
        'mfa_recovery_codes',
        sa.Column('id', UUID, primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code_hash', sa.String(64), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('code_hash', name='uq_mfa_recovery_codes_code_hash'),
    )
    op.create_index('ix_mfa_recovery_codes_user_id', 'mfa_recovery_codes', ['user_id'])
    op.create_index('ix_mfa_recovery_codes_used_at', 'mfa_recovery_codes', ['used_at'])
    op.create_index('ix_mfa_recovery_codes_user_unused', 'mfa_recovery_codes', ['user_id', 'used_at'])


def downgrade():
    op.drop_index('ix_mfa_recovery_codes_user_unused', table_name='mfa_recovery_codes')
    op.drop_index('ix_mfa_recovery_codes_used_at', table_name='mfa_recovery_codes')
    op.drop_index('ix_mfa_recovery_codes_user_id', table_name='mfa_recovery_codes')
    op.drop_table('mfa_recovery_codes')

    op.drop_index('ix_auth_sessions_mfa_verified_at', table_name='auth_sessions')
    op.drop_column('auth_sessions', 'mfa_verified_at')

    op.drop_index('ix_users_mfa_enabled_at', table_name='users')
    op.drop_column('users', 'mfa_last_used_timecode')
    op.drop_column('users', 'mfa_enabled_at')
    op.drop_column('users', 'mfa_pending_secret_encrypted')
    op.drop_column('users', 'mfa_secret_encrypted')
