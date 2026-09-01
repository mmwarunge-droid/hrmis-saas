"""add verified onboarding video watch progress

Revision ID: 028_video_watch_progress
Revises: 027_onboarding_training
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa


revision = '028_video_watch_progress'
down_revision = '027_onboarding_training'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'onboarding_resources',
        sa.Column('duration_seconds', sa.Float(), nullable=True),
    )

    op.add_column(
        'employee_onboarding_tasks',
        sa.Column(
            'video_verified_seconds',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column(
            'video_last_position_seconds',
            sa.Float(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column('video_last_heartbeat_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column('video_started_at', sa.DateTime(), nullable=True),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column('video_completed_at', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column('employee_onboarding_tasks', 'video_completed_at')
    op.drop_column('employee_onboarding_tasks', 'video_started_at')
    op.drop_column('employee_onboarding_tasks', 'video_last_heartbeat_at')
    op.drop_column(
        'employee_onboarding_tasks',
        'video_last_position_seconds',
    )
    op.drop_column('employee_onboarding_tasks', 'video_verified_seconds')
    op.drop_column('onboarding_resources', 'duration_seconds')
