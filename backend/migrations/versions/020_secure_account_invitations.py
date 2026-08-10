"""add secure account invitation lifecycle

Revision ID: 020_secure_account_invitations
Revises: 019_goals_kpi_mvp
Create Date: 2026-08-10
"""

from alembic import op
import sqlalchemy as sa


revision = '020_secure_account_invitations'
down_revision = '019_goals_kpi_mvp'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'users',
        sa.Column(
            'activation_required',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'users',
        sa.Column('invited_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('invitation_sent_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('activated_at', sa.DateTime(), nullable=True),
    )
    op.create_index(
        'ix_users_activation_required',
        'users',
        ['activation_required'],
    )
    op.create_index('ix_users_invited_at', 'users', ['invited_at'])
    op.create_index(
        'ix_users_invitation_sent_at',
        'users',
        ['invitation_sent_at'],
    )
    op.create_index('ix_users_activated_at', 'users', ['activated_at'])

    # Every pre-existing account is already provisioned under the legacy
    # credential model. Mark it as activated without altering verification.
    op.execute(sa.text(
        """
        UPDATE users
        SET activated_at = COALESCE(last_login_at, created_at)
        WHERE activated_at IS NULL
        """
    ))

    op.drop_constraint(
        'ck_account_tokens_purpose',
        'account_tokens',
        type_='check',
    )
    op.create_check_constraint(
        'ck_account_tokens_purpose',
        'account_tokens',
        "purpose IN ('password_reset','email_verification','account_invite')",
    )


def downgrade():
    op.execute(sa.text(
        """
        UPDATE account_tokens
        SET consumed_at = COALESCE(consumed_at, CURRENT_TIMESTAMP)
        WHERE purpose = 'account_invite'
        """
    ))
    op.execute(sa.text(
        "DELETE FROM account_tokens WHERE purpose = 'account_invite'"
    ))
    op.drop_constraint(
        'ck_account_tokens_purpose',
        'account_tokens',
        type_='check',
    )
    op.create_check_constraint(
        'ck_account_tokens_purpose',
        'account_tokens',
        "purpose IN ('password_reset','email_verification')",
    )

    op.drop_index('ix_users_activated_at', table_name='users')
    op.drop_index('ix_users_invitation_sent_at', table_name='users')
    op.drop_index('ix_users_invited_at', table_name='users')
    op.drop_index('ix_users_activation_required', table_name='users')
    op.drop_column('users', 'activated_at')
    op.drop_column('users', 'invitation_sent_at')
    op.drop_column('users', 'invited_at')
    op.drop_column('users', 'activation_required')
