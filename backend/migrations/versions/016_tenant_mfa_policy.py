"""add tenant MFA policy and recovery governance

Revision ID: 016_tenant_mfa_policy
Revises: 015_leave_accrual_ledger
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '016_tenant_mfa_policy'
down_revision = '015_leave_accrual_ledger'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'tenants',
        sa.Column(
            'mfa_policy_mode',
            sa.String(length=40),
            nullable=False,
            server_default='optional',
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'mfa_enrollment_grace_days',
            sa.Integer(),
            nullable=False,
            server_default='14',
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'mfa_enforcement_date',
            sa.Date(),
            nullable=True,
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'mfa_policy_updated_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'tenants',
        sa.Column(
            'mfa_policy_updated_by_id',
            UUID,
            nullable=True,
        ),
    )
    op.create_foreign_key(
        'fk_tenants_mfa_policy_updated_by',
        'tenants',
        'users',
        ['mfa_policy_updated_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_tenants_mfa_policy_updated_by_id',
        'tenants',
        ['mfa_policy_updated_by_id'],
    )
    op.create_check_constraint(
        'ck_tenants_mfa_policy_mode',
        'tenants',
        "mfa_policy_mode IN ("
        "'optional','privileged','managers_and_privileged','all_users'"
        ")",
    )
    op.create_check_constraint(
        'ck_tenants_mfa_grace_days',
        'tenants',
        'mfa_enrollment_grace_days >= 0 '
        'AND mfa_enrollment_grace_days <= 365',
    )

    op.add_column(
        'users',
        sa.Column('mfa_reset_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('mfa_reset_by_user_id', UUID, nullable=True),
    )
    op.create_foreign_key(
        'fk_users_mfa_reset_by',
        'users',
        'users',
        ['mfa_reset_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_users_mfa_reset_at',
        'users',
        ['mfa_reset_at'],
    )
    op.create_index(
        'ix_users_mfa_reset_by_user_id',
        'users',
        ['mfa_reset_by_user_id'],
    )

    op.execute(sa.text(
        """
        INSERT INTO permissions (
            id,
            code,
            description,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            source.code,
            source.description,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM (
            VALUES
                (
                    'security:mfa_policy',
                    'Configure organization MFA policy and review compliance'
                ),
                (
                    'security:mfa_reset',
                    'Reset another user MFA enrollment'
                )
        ) AS source(code, description)
        WHERE NOT EXISTS (
            SELECT 1
            FROM permissions
            WHERE permissions.code = source.code
        )
        """
    ))

    op.execute(sa.text(
        """
        INSERT INTO role_permissions (
            id,
            role_id,
            permission_id,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            role.id,
            permission.id,
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM roles AS role
        CROSS JOIN permissions AS permission
        WHERE permission.code IN (
            'security:mfa_policy',
            'security:mfa_reset'
        )
          AND role.name IN (
            'SUPER_ADMIN',
            'ORGANIZATION_OWNER',
            'CLIENT_ADMIN'
        )
          AND NOT EXISTS (
            SELECT 1
            FROM role_permissions AS existing
            WHERE existing.role_id = role.id
              AND existing.permission_id = permission.id
        )
        """
    ))


def downgrade():
    op.execute(sa.text(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id
            FROM permissions
            WHERE code IN (
                'security:mfa_policy',
                'security:mfa_reset'
            )
        )
        """
    ))
    op.execute(sa.text(
        """
        DELETE FROM permissions
        WHERE code IN (
            'security:mfa_policy',
            'security:mfa_reset'
        )
        """
    ))

    op.drop_index(
        'ix_users_mfa_reset_by_user_id',
        table_name='users',
    )
    op.drop_index(
        'ix_users_mfa_reset_at',
        table_name='users',
    )
    op.drop_constraint(
        'fk_users_mfa_reset_by',
        'users',
        type_='foreignkey',
    )
    op.drop_column('users', 'mfa_reset_by_user_id')
    op.drop_column('users', 'mfa_reset_at')

    op.drop_constraint(
        'ck_tenants_mfa_grace_days',
        'tenants',
        type_='check',
    )
    op.drop_constraint(
        'ck_tenants_mfa_policy_mode',
        'tenants',
        type_='check',
    )
    op.drop_index(
        'ix_tenants_mfa_policy_updated_by_id',
        table_name='tenants',
    )
    op.drop_constraint(
        'fk_tenants_mfa_policy_updated_by',
        'tenants',
        type_='foreignkey',
    )
    op.drop_column('tenants', 'mfa_policy_updated_by_id')
    op.drop_column('tenants', 'mfa_policy_updated_at')
    op.drop_column('tenants', 'mfa_enforcement_date')
    op.drop_column('tenants', 'mfa_enrollment_grace_days')
    op.drop_column('tenants', 'mfa_policy_mode')
