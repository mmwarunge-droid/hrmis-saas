"""add onboarding training attempt history and retakes

Revision ID: 029_training_attempts
Revises: 028_video_watch_progress
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '029_training_attempts'
down_revision = '028_video_watch_progress'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'onboarding_tasks',
        sa.Column(
            'max_attempts',
            sa.Integer(),
            nullable=False,
            server_default='1',
        ),
    )
    op.add_column(
        'onboarding_tasks',
        sa.Column('pass_mark_percent', sa.Float(), nullable=True),
    )
    op.create_check_constraint(
        'ck_onboarding_tasks_max_attempts',
        'onboarding_tasks',
        'max_attempts >= 1 AND max_attempts <= 20',
    )
    op.create_check_constraint(
        'ck_onboarding_tasks_pass_mark',
        'onboarding_tasks',
        'pass_mark_percent IS NULL OR '
        '(pass_mark_percent >= 0 AND pass_mark_percent <= 100)',
    )

    op.add_column(
        'employee_onboarding_tasks',
        sa.Column(
            'current_attempt_number',
            sa.Integer(),
            nullable=False,
            server_default='1',
        ),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column(
            'additional_attempts_granted',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.create_check_constraint(
        'ck_employee_onboarding_current_attempt',
        'employee_onboarding_tasks',
        'current_attempt_number >= 1',
    )
    op.create_check_constraint(
        'ck_employee_onboarding_extra_attempts',
        'employee_onboarding_tasks',
        'additional_attempts_granted >= 0',
    )

    op.create_table(
        'onboarding_training_attempts',
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
            'assignment_id',
            UUID,
            sa.ForeignKey(
                'employee_onboarding_tasks.id',
                ondelete='CASCADE',
            ),
            nullable=False,
        ),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default='pending',
        ),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('score_percent', sa.Float(), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column(
            'time_spent_seconds',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'authorized_by_user_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('authorization_reason', sa.Text(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.UniqueConstraint(
            'tenant_id',
            'assignment_id',
            'attempt_number',
            name='uq_onboarding_training_attempt_number',
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','failed',"
            "'superseded','waived')",
            name='ck_onboarding_training_attempt_status',
        ),
        sa.CheckConstraint(
            'attempt_number >= 1',
            name='ck_onboarding_training_attempt_number',
        ),
        sa.CheckConstraint(
            'score_percent IS NULL OR '
            '(score_percent >= 0 AND score_percent <= 100)',
            name='ck_onboarding_training_attempt_score',
        ),
    )
    op.create_index(
        'ix_onboarding_training_attempts_tenant_id',
        'onboarding_training_attempts',
        ['tenant_id'],
    )
    op.create_index(
        'ix_onboarding_training_attempts_assignment_id',
        'onboarding_training_attempts',
        ['assignment_id'],
    )
    op.create_index(
        'ix_onboarding_training_attempts_status',
        'onboarding_training_attempts',
        ['status'],
    )
    op.create_index(
        'ix_onboarding_training_attempts_authorized_by_user_id',
        'onboarding_training_attempts',
        ['authorized_by_user_id'],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO onboarding_training_attempts (
                tenant_id, assignment_id, attempt_number, status,
                started_at, completed_at, passed, time_spent_seconds,
                authorization_reason
            )
            SELECT
                tenant_id,
                id,
                1,
                CASE
                    WHEN status = 'completed' THEN 'completed'
                    WHEN status = 'waived' THEN 'waived'
                    WHEN status = 'in_progress' THEN 'in_progress'
                    ELSE 'pending'
                END,
                COALESCE(video_started_at, resource_viewed_at, created_at),
                completed_at,
                CASE WHEN status = 'completed' THEN true ELSE NULL END,
                COALESCE(video_verified_seconds, 0),
                'Initial assignment history backfill'
            FROM employee_onboarding_tasks
            """
        )
    )


def downgrade():
    op.drop_index(
        'ix_onboarding_training_attempts_authorized_by_user_id',
        table_name='onboarding_training_attempts',
    )
    op.drop_index(
        'ix_onboarding_training_attempts_status',
        table_name='onboarding_training_attempts',
    )
    op.drop_index(
        'ix_onboarding_training_attempts_assignment_id',
        table_name='onboarding_training_attempts',
    )
    op.drop_index(
        'ix_onboarding_training_attempts_tenant_id',
        table_name='onboarding_training_attempts',
    )
    op.drop_table('onboarding_training_attempts')

    op.drop_constraint(
        'ck_employee_onboarding_extra_attempts',
        'employee_onboarding_tasks',
        type_='check',
    )
    op.drop_constraint(
        'ck_employee_onboarding_current_attempt',
        'employee_onboarding_tasks',
        type_='check',
    )
    op.drop_column(
        'employee_onboarding_tasks',
        'additional_attempts_granted',
    )
    op.drop_column(
        'employee_onboarding_tasks',
        'current_attempt_number',
    )

    op.drop_constraint(
        'ck_onboarding_tasks_pass_mark',
        'onboarding_tasks',
        type_='check',
    )
    op.drop_constraint(
        'ck_onboarding_tasks_max_attempts',
        'onboarding_tasks',
        type_='check',
    )
    op.drop_column('onboarding_tasks', 'pass_mark_percent')
    op.drop_column('onboarding_tasks', 'max_attempts')
