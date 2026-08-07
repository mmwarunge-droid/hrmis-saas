"""add goals and KPI tracking

Revision ID: 019_goals_kpi_mvp
Revises: 018_workflow_notifications
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '019_goals_kpi_mvp'
down_revision = '018_workflow_notifications'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def timestamp_columns():
    return (
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
    )


def upgrade():
    op.create_table(
        'goals',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_type', sa.String(length=30), nullable=False, server_default='employee'),
        sa.Column('employee_id', UUID, sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=True),
        sa.Column('department_id', UUID, sa.ForeignKey('departments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by_user_id', UUID, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='active'),
        sa.Column('health', sa.String(length=30), nullable=False, server_default='on_track'),
        sa.Column('target_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('current_value', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('unit', sa.String(length=40), nullable=False, server_default='%'),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('progress_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('weight', sa.Numeric(5, 2), nullable=False, server_default='100'),
        sa.Column('last_check_in_at', sa.DateTime(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("owner_type IN ('organization','department','employee')", name='ck_goals_owner_type'),
        sa.CheckConstraint("status IN ('draft','active','completed','cancelled')", name='ck_goals_status'),
        sa.CheckConstraint("health IN ('on_track','at_risk','off_track','completed')", name='ck_goals_health'),
        sa.CheckConstraint('target_value > 0', name='ck_goals_target_positive'),
        sa.CheckConstraint('progress_percent BETWEEN 0 AND 100', name='ck_goals_progress_range'),
        sa.CheckConstraint('weight BETWEEN 0 AND 100', name='ck_goals_weight_range'),
        sa.CheckConstraint(
            "(owner_type = 'organization' AND employee_id IS NULL AND department_id IS NULL) OR "
            "(owner_type = 'department' AND department_id IS NOT NULL AND employee_id IS NULL) OR "
            "(owner_type = 'employee' AND employee_id IS NOT NULL)",
            name='ck_goals_owner_reference',
        ),
    )
    for column in ('tenant_id', 'owner_type', 'employee_id', 'department_id', 'created_by_user_id', 'status', 'health', 'due_date'):
        op.create_index(f'ix_goals_{column}', 'goals', [column])

    op.create_table(
        'goal_check_ins',
        sa.Column('id', UUID, primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID, sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('goal_id', UUID, sa.ForeignKey('goals.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_user_id', UUID, sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('current_value', sa.Numeric(14, 2), nullable=False),
        sa.Column('progress_percent', sa.Numeric(5, 2), nullable=False),
        sa.Column('health', sa.String(length=30), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint('progress_percent BETWEEN 0 AND 100', name='ck_goal_check_ins_progress_range'),
        sa.CheckConstraint("health IN ('on_track','at_risk','off_track','completed')", name='ck_goal_check_ins_health'),
    )
    op.create_index('ix_goal_check_ins_tenant_id', 'goal_check_ins', ['tenant_id'])
    op.create_index('ix_goal_check_ins_goal_id', 'goal_check_ins', ['goal_id'])
    op.create_index('ix_goal_check_ins_actor_user_id', 'goal_check_ins', ['actor_user_id'])

    permissions = (
        ('goal:read', 'Read goals and KPI progress'),
        ('goal:manage', 'Create and manage goals'),
        ('goal:checkin', 'Record goal progress check-ins'),
    )
    for code, description in permissions:
        op.execute(sa.text(
            """
            INSERT INTO permissions (id, code, description, created_at, updated_at)
            SELECT gen_random_uuid(), :code, :description, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)
            """
        ).bindparams(code=code, description=description))

    role_permissions = {
        'SUPER_ADMIN': ('goal:read', 'goal:manage', 'goal:checkin'),
        'ORGANIZATION_OWNER': ('goal:read', 'goal:manage', 'goal:checkin'),
        'HR_CONSULTANT': ('goal:read', 'goal:manage', 'goal:checkin'),
        'CLIENT_ADMIN': ('goal:read', 'goal:manage', 'goal:checkin'),
        'MANAGER': ('goal:read', 'goal:manage', 'goal:checkin'),
        'EMPLOYEE': ('goal:read', 'goal:checkin'),
    }
    for role_name, codes in role_permissions.items():
        for code in codes:
            op.execute(sa.text(
                """
                INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at)
                SELECT gen_random_uuid(), role.id, permission.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM roles AS role
                CROSS JOIN permissions AS permission
                WHERE role.name = :role_name
                  AND permission.code = :code
                  AND NOT EXISTS (
                    SELECT 1 FROM role_permissions AS existing
                    WHERE existing.role_id = role.id
                      AND existing.permission_id = permission.id
                  )
                """
            ).bindparams(role_name=role_name, code=code))


def downgrade():
    op.drop_table('goal_check_ins')
    op.drop_table('goals')
    op.execute(sa.text(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (
            SELECT id FROM permissions
            WHERE code IN ('goal:read','goal:manage','goal:checkin')
        )
        """
    ))
    op.execute(sa.text(
        "DELETE FROM permissions WHERE code IN ('goal:read','goal:manage','goal:checkin')"
    ))
