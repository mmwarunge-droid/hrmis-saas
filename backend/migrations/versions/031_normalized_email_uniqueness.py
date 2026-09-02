"""enforce normalized email uniqueness

Revision ID: 031_normalized_email_uniqueness
Revises: 030_signature_resends
Create Date: 2026-09-02
"""

from alembic import op
import sqlalchemy as sa


revision = '031_normalized_email_uniqueness'
down_revision = '030_signature_resends'
branch_labels = None
depends_on = None


def _assert_no_normalized_duplicates(bind):
    duplicate_user = bind.execute(sa.text(
        """
        SELECT 1
        FROM users
        GROUP BY lower(trim(email))
        HAVING count(*) > 1
        LIMIT 1
        """
    )).first()
    if duplicate_user:
        raise RuntimeError(
            'Cannot enforce normalized user-email uniqueness: '
            'duplicate normalized user emails exist. Run the duplicate-email '
            'audit and resolve the records before retrying the migration.'
        )

    duplicate_employee = bind.execute(sa.text(
        """
        SELECT 1
        FROM employees
        GROUP BY tenant_id, lower(trim(email))
        HAVING count(*) > 1
        LIMIT 1
        """
    )).first()
    if duplicate_employee:
        raise RuntimeError(
            'Cannot enforce normalized employee-email uniqueness: '
            'duplicate normalized employee emails exist within a tenant. '
            'Run the duplicate-email audit and resolve the records before '
            'retrying the migration.'
        )


def upgrade():
    bind = op.get_bind()
    _assert_no_normalized_duplicates(bind)

    # Canonicalize existing values before adding expression indexes. The
    # production audit preceding this migration confirmed there are no
    # normalized collisions, so this does not merge or delete any record.
    op.execute(sa.text(
        "UPDATE users SET email = lower(trim(email))"
    ))
    op.execute(sa.text(
        "UPDATE employees SET email = lower(trim(email))"
    ))

    op.execute(sa.text(
        """
        CREATE UNIQUE INDEX uq_users_email_normalized
        ON users (lower(trim(email)))
        """
    ))
    op.execute(sa.text(
        """
        CREATE UNIQUE INDEX uq_employees_tenant_email_normalized
        ON employees (tenant_id, lower(trim(email)))
        """
    ))


def downgrade():
    op.drop_index(
        'uq_employees_tenant_email_normalized',
        table_name='employees',
    )
    op.drop_index(
        'uq_users_email_normalized',
        table_name='users',
    )
