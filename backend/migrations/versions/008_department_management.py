"""add department leadership support

Revision ID: 008_department_management
Revises: 007_privileged_mfa
Create Date: 2026-07-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008_department_management'
down_revision = '007_privileged_mfa'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column('departments', sa.Column('head_employee_id', UUID, nullable=True))
    op.create_foreign_key(
        'fk_departments_head_employee_id_employees',
        'departments',
        'employees',
        ['head_employee_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index('ix_departments_head_employee_id', 'departments', ['head_employee_id'])


def downgrade():
    op.drop_index('ix_departments_head_employee_id', table_name='departments')
    op.drop_constraint('fk_departments_head_employee_id_employees', 'departments', type_='foreignkey')
    op.drop_column('departments', 'head_employee_id')
