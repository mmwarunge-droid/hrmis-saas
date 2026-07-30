"""add leave accrual ledger and reservations

Revision ID: 015_leave_accrual_ledger
Revises: 014_leave_owner_governance
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '015_leave_accrual_ledger'
down_revision = '014_leave_owner_governance'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)

LEDGER_EVENT_CHECK = (
    "event_type IN ("
    "'BASELINE_IMPORT','OPENING_BALANCE','ACCRUAL','CARRYOVER',"
    "'MANUAL_ADJUSTMENT','REQUEST_RESERVED','REQUEST_APPROVED',"
    "'REQUEST_CANCELLED','REQUEST_RESTORED','EXPIRY'"
    ")"
)


def upgrade():
    op.add_column(
        'leave_types',
        sa.Column(
            'carryover_expiry_months',
            sa.Integer(),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        'ck_leave_types_carryover_expiry_months',
        'leave_types',
        'carryover_expiry_months IS NULL '
        'OR carryover_expiry_months >= 0',
    )
    op.execute(sa.text(
        """
        UPDATE leave_types
        SET carryover_expiry_months = 3
        WHERE code = 'annual_leave'
          AND carryover_allowed = true
        """
    ))

    for name in [
        'opening_days',
        'carried_over_days',
        'adjusted_days',
        'reserved_days',
        'expired_days',
        'carryover_remaining_days',
    ]:
        op.add_column(
            'leave_balances',
            sa.Column(
                name,
                sa.Numeric(8, 2),
                nullable=False,
                server_default='0',
            ),
        )

    op.add_column(
        'leave_balances',
        sa.Column(
            'carryover_expires_at',
            sa.Date(),
            nullable=True,
        ),
    )
    op.add_column(
        'leave_balances',
        sa.Column(
            'accrual_through_date',
            sa.Date(),
            nullable=True,
        ),
    )
    op.create_index(
        'ix_leave_balances_carryover_expires_at',
        'leave_balances',
        ['carryover_expires_at'],
    )
    op.create_index(
        'ix_leave_balances_accrual_through_date',
        'leave_balances',
        ['accrual_through_date'],
    )
    op.create_check_constraint(
        'ck_leave_balances_reserved_nonnegative',
        'leave_balances',
        'reserved_days >= 0',
    )
    op.create_check_constraint(
        'ck_leave_balances_carryover_remaining_nonnegative',
        'leave_balances',
        'carryover_remaining_days >= 0',
    )

    op.add_column(
        'leave_requests',
        sa.Column(
            'balance_reserved_at',
            sa.DateTime(),
            nullable=True,
        ),
    )
    op.add_column(
        'leave_requests',
        sa.Column(
            'reserved_carryover_days',
            sa.Numeric(8, 2),
            nullable=False,
            server_default='0',
        ),
    )
    op.create_index(
        'ix_leave_requests_balance_reserved_at',
        'leave_requests',
        ['balance_reserved_at'],
    )
    op.create_check_constraint(
        'ck_leave_requests_reserved_carryover_nonnegative',
        'leave_requests',
        'reserved_carryover_days >= 0',
    )

    op.create_table(
        'leave_ledger_entries',
        sa.Column(
            'id',
            UUID,
            primary_key=True,
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'tenant_id',
            UUID,
            sa.ForeignKey('tenants.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'employee_id',
            UUID,
            sa.ForeignKey('employees.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'leave_type_id',
            UUID,
            sa.ForeignKey('leave_types.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'leave_balance_id',
            UUID,
            sa.ForeignKey('leave_balances.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'leave_request_id',
            UUID,
            sa.ForeignKey('leave_requests.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'actor_user_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column(
            'event_type',
            sa.String(length=40),
            nullable=False,
        ),
        sa.Column(
            'amount_days',
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            'balance_after_days',
            sa.Numeric(10, 2),
            nullable=False,
        ),
        sa.Column(
            'effective_date',
            sa.Date(),
            nullable=False,
        ),
        sa.Column(
            'year',
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            'idempotency_key',
            sa.String(length=180),
            nullable=False,
        ),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column(
            'metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'idempotency_key',
            name='uq_leave_ledger_tenant_idempotency',
        ),
        sa.CheckConstraint(
            LEDGER_EVENT_CHECK,
            name='ck_leave_ledger_event_type',
        ),
    )

    for name, columns in [
        ('ix_leave_ledger_entries_tenant_id', ['tenant_id']),
        ('ix_leave_ledger_entries_employee_id', ['employee_id']),
        ('ix_leave_ledger_entries_leave_type_id', ['leave_type_id']),
        ('ix_leave_ledger_entries_leave_balance_id', ['leave_balance_id']),
        ('ix_leave_ledger_entries_leave_request_id', ['leave_request_id']),
        ('ix_leave_ledger_entries_actor_user_id', ['actor_user_id']),
        ('ix_leave_ledger_entries_event_type', ['event_type']),
        ('ix_leave_ledger_entries_effective_date', ['effective_date']),
        ('ix_leave_ledger_entries_year', ['year']),
    ]:
        op.create_index(name, 'leave_ledger_entries', columns)

    op.execute(sa.text(
        """
        UPDATE leave_balances AS balance
        SET opening_days = CASE
                WHEN policy.entitlement_mode = 'accrued'
                    THEN 0
                ELSE balance.accrued_days
            END,
            accrued_days = CASE
                WHEN policy.entitlement_mode = 'accrued'
                    THEN balance.accrued_days
                ELSE 0
            END,
            accrual_through_date = CASE
                WHEN balance.year < EXTRACT(YEAR FROM CURRENT_DATE)
                    THEN make_date(balance.year, 12, 31)
                WHEN balance.year = EXTRACT(YEAR FROM CURRENT_DATE)
                    THEN (
                        date_trunc('month', CURRENT_DATE)
                        + interval '1 month - 1 day'
                    )::date
                ELSE NULL
            END
        FROM leave_types AS policy
        WHERE policy.id = balance.leave_type_id
        """
    ))

    op.execute(sa.text(
        """
        INSERT INTO leave_ledger_entries (
            id,
            tenant_id,
            employee_id,
            leave_type_id,
            leave_balance_id,
            event_type,
            amount_days,
            balance_after_days,
            effective_date,
            year,
            idempotency_key,
            reason,
            metadata_json,
            created_at,
            updated_at
        )
        SELECT
            gen_random_uuid(),
            balance.tenant_id,
            balance.employee_id,
            balance.leave_type_id,
            balance.id,
            'BASELINE_IMPORT',
            balance.balance_days,
            balance.balance_days,
            CASE
                WHEN balance.year = EXTRACT(YEAR FROM CURRENT_DATE)
                    THEN CURRENT_DATE
                ELSE make_date(balance.year, 1, 1)
            END,
            balance.year,
            'baseline:' || balance.id::text,
            'Balance imported when the allocation ledger was enabled',
            json_build_object(
                'opening_days', balance.opening_days,
                'accrued_days', balance.accrued_days,
                'used_days', balance.used_days
            ),
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM leave_balances AS balance
        """
    ))

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
                    'leave:ledger',
                    'Read leave allocation ledger entries'
                ),
                (
                    'leave:adjust',
                    'Adjust leave balances and run allocations'
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
        WHERE (
            (
                permission.code = 'leave:ledger'
                AND role.name IN (
                    'SUPER_ADMIN',
                    'ORGANIZATION_OWNER',
                    'HR_CONSULTANT',
                    'CLIENT_ADMIN',
                    'MANAGER',
                    'EMPLOYEE'
                )
            ) OR (
                permission.code = 'leave:adjust'
                AND role.name IN (
                    'SUPER_ADMIN',
                    'ORGANIZATION_OWNER',
                    'HR_CONSULTANT',
                    'CLIENT_ADMIN'
                )
            )
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
            WHERE code IN ('leave:ledger', 'leave:adjust')
        )
        """
    ))
    op.execute(sa.text(
        """
        DELETE FROM permissions
        WHERE code IN ('leave:ledger', 'leave:adjust')
        """
    ))

    op.drop_table('leave_ledger_entries')

    op.drop_constraint(
        'ck_leave_requests_reserved_carryover_nonnegative',
        'leave_requests',
        type_='check',
    )
    op.drop_index(
        'ix_leave_requests_balance_reserved_at',
        table_name='leave_requests',
    )
    op.drop_column('leave_requests', 'reserved_carryover_days')
    op.drop_column('leave_requests', 'balance_reserved_at')

    op.drop_constraint(
        'ck_leave_balances_carryover_remaining_nonnegative',
        'leave_balances',
        type_='check',
    )
    op.drop_constraint(
        'ck_leave_balances_reserved_nonnegative',
        'leave_balances',
        type_='check',
    )
    op.drop_index(
        'ix_leave_balances_accrual_through_date',
        table_name='leave_balances',
    )
    op.drop_index(
        'ix_leave_balances_carryover_expires_at',
        table_name='leave_balances',
    )
    op.drop_column('leave_balances', 'accrual_through_date')
    op.drop_column('leave_balances', 'carryover_expires_at')
    for name in [
        'carryover_remaining_days',
        'expired_days',
        'reserved_days',
        'adjusted_days',
        'carried_over_days',
        'opening_days',
    ]:
        op.drop_column('leave_balances', name)

    op.drop_constraint(
        'ck_leave_types_carryover_expiry_months',
        'leave_types',
        type_='check',
    )
    op.drop_column('leave_types', 'carryover_expiry_months')
