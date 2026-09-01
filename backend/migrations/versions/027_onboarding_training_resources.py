"""add onboarding training resources and acknowledgements

Revision ID: 027_onboarding_training
Revises: 026_job_title_governance
Create Date: 2026-09-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '027_onboarding_training'
down_revision = '026_job_title_governance'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.create_table(
        'onboarding_resources',
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
            'uploaded_by_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('resource_type', sa.String(length=20), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('stored_filename', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
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
            'stored_filename',
            name='uq_onboarding_resources_stored_filename',
        ),
        sa.CheckConstraint(
            "resource_type IN ('document','video')",
            name='ck_onboarding_resources_type',
        ),
    )
    op.create_index(
        'ix_onboarding_resources_tenant_id',
        'onboarding_resources',
        ['tenant_id'],
    )
    op.create_index(
        'ix_onboarding_resources_uploaded_by_id',
        'onboarding_resources',
        ['uploaded_by_id'],
    )
    op.create_index(
        'ix_onboarding_resources_resource_type',
        'onboarding_resources',
        ['resource_type'],
    )

    op.add_column(
        'onboarding_tasks',
        sa.Column(
            'task_type',
            sa.String(length=20),
            nullable=False,
            server_default='action',
        ),
    )
    op.add_column(
        'onboarding_tasks',
        sa.Column('resource_id', UUID, nullable=True),
    )
    op.add_column(
        'onboarding_tasks',
        sa.Column(
            'requires_acknowledgement',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.create_foreign_key(
        'fk_onboarding_tasks_resource_id',
        'onboarding_tasks',
        'onboarding_resources',
        ['resource_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_onboarding_tasks_resource_id',
        'onboarding_tasks',
        ['resource_id'],
    )
    op.create_check_constraint(
        'ck_onboarding_tasks_type',
        'onboarding_tasks',
        "task_type IN ('action','document','video')",
    )

    op.add_column(
        'employee_onboarding_tasks',
        sa.Column('resource_viewed_at', sa.DateTime(timezone=True)),
    )
    op.add_column(
        'employee_onboarding_tasks',
        sa.Column('acknowledged_at', sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_column('employee_onboarding_tasks', 'acknowledged_at')
    op.drop_column('employee_onboarding_tasks', 'resource_viewed_at')

    op.drop_constraint(
        'ck_onboarding_tasks_type',
        'onboarding_tasks',
        type_='check',
    )
    op.drop_index('ix_onboarding_tasks_resource_id', table_name='onboarding_tasks')
    op.drop_constraint(
        'fk_onboarding_tasks_resource_id',
        'onboarding_tasks',
        type_='foreignkey',
    )
    op.drop_column('onboarding_tasks', 'requires_acknowledgement')
    op.drop_column('onboarding_tasks', 'resource_id')
    op.drop_column('onboarding_tasks', 'task_type')

    op.drop_index(
        'ix_onboarding_resources_resource_type',
        table_name='onboarding_resources',
    )
    op.drop_index(
        'ix_onboarding_resources_uploaded_by_id',
        table_name='onboarding_resources',
    )
    op.drop_index(
        'ix_onboarding_resources_tenant_id',
        table_name='onboarding_resources',
    )
    op.drop_table('onboarding_resources')
