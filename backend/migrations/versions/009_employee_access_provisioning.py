"""Enforce one user account per employee profile.

Revision ID: 009_employee_access_provisioning
Revises: 008_department_management
"""

from alembic import op

revision = '009_employee_access_provisioning'
down_revision = '008_department_management'
branch_labels = None
depends_on = None


def upgrade():
    op.create_unique_constraint('uq_employees_user_id', 'employees', ['user_id'])


def downgrade():
    op.drop_constraint('uq_employees_user_id', 'employees', type_='unique')
