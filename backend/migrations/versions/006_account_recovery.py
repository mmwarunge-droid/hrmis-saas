"""add account recovery and email verification tokens

Revision ID: 006_account_recovery
Revises: 005_login_security
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '006_account_recovery'
down_revision = '005_login_security'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_users_email_verified_at', 'users', ['email_verified_at'])

    op.create_table(
        'account_tokens',
        sa.Column('id', UUID, primary_key=True, nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', UUID, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('purpose', sa.String(40), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint(
            "purpose IN ('password_reset','email_verification')",
            name='ck_account_tokens_purpose',
        ),
        sa.UniqueConstraint('token_hash', name='uq_account_tokens_token_hash'),
    )
    op.create_index('ix_account_tokens_tenant_id', 'account_tokens', ['tenant_id'])
    op.create_index('ix_account_tokens_user_id', 'account_tokens', ['user_id'])
    op.create_index('ix_account_tokens_purpose', 'account_tokens', ['purpose'])
    op.create_index('ix_account_tokens_expires_at', 'account_tokens', ['expires_at'])
    op.create_index('ix_account_tokens_consumed_at', 'account_tokens', ['consumed_at'])
    op.create_index(
        'ix_account_tokens_user_purpose_active',
        'account_tokens',
        ['user_id', 'purpose', 'consumed_at', 'expires_at'],
    )


def downgrade():
    op.drop_index('ix_account_tokens_user_purpose_active', table_name='account_tokens')
    op.drop_index('ix_account_tokens_consumed_at', table_name='account_tokens')
    op.drop_index('ix_account_tokens_expires_at', table_name='account_tokens')
    op.drop_index('ix_account_tokens_purpose', table_name='account_tokens')
    op.drop_index('ix_account_tokens_user_id', table_name='account_tokens')
    op.drop_index('ix_account_tokens_tenant_id', table_name='account_tokens')
    op.drop_table('account_tokens')
    op.drop_index('ix_users_email_verified_at', table_name='users')
    op.drop_column('users', 'email_verified_at')
