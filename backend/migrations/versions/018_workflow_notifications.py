"""add actionable workflow notifications

Revision ID: 018_workflow_notifications
Revises: 017_employee_homepage
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa


revision = '018_workflow_notifications'
down_revision = '017_employee_homepage'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'notifications',
        sa.Column(
            'priority',
            sa.String(length=20),
            nullable=False,
            server_default='normal',
        ),
    )
    op.add_column(
        'notifications',
        sa.Column('action_url', sa.String(length=500), nullable=True),
    )
    op.add_column(
        'notifications',
        sa.Column(
            'metadata_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'::json"),
        ),
    )
    op.create_index(
        'ix_notifications_notification_type',
        'notifications',
        ['notification_type'],
    )
    op.create_index(
        'ix_notifications_read_at',
        'notifications',
        ['read_at'],
    )
    op.create_check_constraint(
        'ck_notifications_priority',
        'notifications',
        "priority IN ('low','normal','high','urgent')",
    )


def downgrade():
    op.drop_constraint(
        'ck_notifications_priority',
        'notifications',
        type_='check',
    )
    op.drop_index('ix_notifications_read_at', table_name='notifications')
    op.drop_index(
        'ix_notifications_notification_type',
        table_name='notifications',
    )
    op.drop_column('notifications', 'metadata_json')
    op.drop_column('notifications', 'action_url')
    op.drop_column('notifications', 'priority')
