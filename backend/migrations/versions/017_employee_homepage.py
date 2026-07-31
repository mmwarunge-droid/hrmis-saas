"""add employee homepage, profiles, events and essentials

Revision ID: 017_employee_homepage
Revises: 016_tenant_mfa_policy
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '017_employee_homepage'
down_revision = '016_tenant_mfa_policy'
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
        WHERE role.name = 'EMPLOYEE'
          AND permission.code = 'dashboard:read'
          AND NOT EXISTS (
              SELECT 1
              FROM role_permissions AS existing
              WHERE existing.role_id = role.id
                AND existing.permission_id = permission.id
          )
        """
    ))

    op.add_column(
        'employees',
        sa.Column(
            'birthday_visibility',
            sa.String(length=30),
            nullable=False,
            server_default='colleagues',
        ),
    )
    op.add_column(
        'employees',
        sa.Column('profile_photo_url', sa.String(length=1000), nullable=True),
    )
    op.add_column(
        'employees',
        sa.Column('profile_cover_url', sa.String(length=1000), nullable=True),
    )
    op.add_column('employees', sa.Column('biography', sa.Text(), nullable=True))
    op.add_column(
        'employees',
        sa.Column(
            'hobbies_json',
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.add_column(
        'employees',
        sa.Column('gender_identity', sa.String(length=40), nullable=True),
    )
    op.add_column(
        'employees',
        sa.Column(
            'gender_self_description',
            sa.String(length=120),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        'ck_employees_birthday_visibility',
        'employees',
        "birthday_visibility IN ('colleagues','hr_only','hidden')",
    )
    op.create_check_constraint(
        'ck_employees_gender_identity',
        'employees',
        "gender_identity IS NULL OR gender_identity IN ("
        "'woman','man','non_binary','self_described','prefer_not_to_say'"
        ")",
    )

    op.create_table(
        'tenant_homepage_settings',
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
        sa.Column('banner_url', sa.String(length=1000), nullable=True),
        sa.Column('logo_url', sa.String(length=1000), nullable=True),
        sa.Column(
            'welcome_message',
            sa.String(length=240),
            nullable=False,
            server_default='Glad you are here.',
        ),
        sa.Column(
            'enabled_sections',
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'[\"birthdays\",\"essentials\",\"people_out_today\","
                "\"events_this_week\",\"new_hires\",\"anniversaries\","
                "\"our_people\"]'::json",
            ),
        ),
        sa.Column(
            'section_order',
            sa.JSON(),
            nullable=False,
            server_default=sa.text(
                "'[\"birthdays\",\"essentials\",\"people_out_today\","
                "\"events_this_week\",\"new_hires\",\"anniversaries\","
                "\"our_people\"]'::json",
            ),
        ),
        sa.Column(
            'new_hire_window_days',
            sa.Integer(),
            nullable=False,
            server_default='30',
        ),
        sa.Column(
            'birthday_visibility_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            'anniversaries_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            'people_statistics_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.Column(
            'assistant_enabled',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column('assistant_url', sa.String(length=1000), nullable=True),
        *timestamp_columns(),
        sa.UniqueConstraint('tenant_id', name='uq_tenant_homepage_settings_tenant'),
        sa.CheckConstraint(
            'new_hire_window_days BETWEEN 7 AND 180',
            name='ck_tenant_homepage_new_hire_window',
        ),
    )
    op.create_index(
        'ix_tenant_homepage_settings_tenant_id',
        'tenant_homepage_settings',
        ['tenant_id'],
    )

    op.create_table(
        'organization_events',
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
        sa.Column('title', sa.String(length=180), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('starts_at', sa.DateTime(), nullable=False),
        sa.Column('ends_at', sa.DateTime(), nullable=True),
        sa.Column('location', sa.String(length=240), nullable=True),
        sa.Column('meeting_url', sa.String(length=1000), nullable=True),
        sa.Column('image_url', sa.String(length=1000), nullable=True),
        sa.Column(
            'audience',
            sa.String(length=40),
            nullable=False,
            server_default='all',
        ),
        sa.Column(
            'status',
            sa.String(length=30),
            nullable=False,
            server_default='draft',
        ),
        sa.Column(
            'created_by_id',
            UUID,
            sa.ForeignKey('users.id', ondelete='SET NULL'),
            nullable=True,
        ),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "status IN ('draft','published','cancelled')",
            name='ck_organization_events_status',
        ),
        sa.CheckConstraint(
            "audience IN ('all','employees','managers')",
            name='ck_organization_events_audience',
        ),
        sa.CheckConstraint(
            'ends_at IS NULL OR ends_at >= starts_at',
            name='ck_organization_events_range',
        ),
    )
    op.create_index(
        'ix_organization_events_tenant_id',
        'organization_events',
        ['tenant_id'],
    )
    op.create_index(
        'ix_organization_events_starts_at',
        'organization_events',
        ['starts_at'],
    )
    op.create_index(
        'ix_organization_events_status',
        'organization_events',
        ['status'],
    )

    op.create_table(
        'homepage_essentials',
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
            'document_id',
            UUID,
            sa.ForeignKey('documents.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('display_title', sa.String(length=180), nullable=True),
        sa.Column(
            'display_order',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
        sa.Column(
            'importance',
            sa.String(length=30),
            nullable=False,
            server_default='recommended',
        ),
        sa.Column(
            'is_published',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        *timestamp_columns(),
        sa.UniqueConstraint(
            'tenant_id',
            'document_id',
            name='uq_homepage_essentials_tenant_document',
        ),
        sa.CheckConstraint(
            "importance IN ('required','recommended')",
            name='ck_homepage_essentials_importance',
        ),
    )
    op.create_index(
        'ix_homepage_essentials_tenant_id',
        'homepage_essentials',
        ['tenant_id'],
    )
    op.create_index(
        'ix_homepage_essentials_document_id',
        'homepage_essentials',
        ['document_id'],
    )


def downgrade():
    op.execute(sa.text(
        """
        DELETE FROM role_permissions
        WHERE role_id IN (SELECT id FROM roles WHERE name = 'EMPLOYEE')
          AND permission_id IN (
              SELECT id FROM permissions WHERE code = 'dashboard:read'
          )
        """
    ))

    op.drop_index(
        'ix_homepage_essentials_document_id',
        table_name='homepage_essentials',
    )
    op.drop_index(
        'ix_homepage_essentials_tenant_id',
        table_name='homepage_essentials',
    )
    op.drop_table('homepage_essentials')

    op.drop_index(
        'ix_organization_events_status',
        table_name='organization_events',
    )
    op.drop_index(
        'ix_organization_events_starts_at',
        table_name='organization_events',
    )
    op.drop_index(
        'ix_organization_events_tenant_id',
        table_name='organization_events',
    )
    op.drop_table('organization_events')

    op.drop_index(
        'ix_tenant_homepage_settings_tenant_id',
        table_name='tenant_homepage_settings',
    )
    op.drop_table('tenant_homepage_settings')

    op.drop_constraint(
        'ck_employees_gender_identity',
        'employees',
        type_='check',
    )
    op.drop_constraint(
        'ck_employees_birthday_visibility',
        'employees',
        type_='check',
    )
    op.drop_column('employees', 'gender_self_description')
    op.drop_column('employees', 'gender_identity')
    op.drop_column('employees', 'hobbies_json')
    op.drop_column('employees', 'biography')
    op.drop_column('employees', 'profile_cover_url')
    op.drop_column('employees', 'profile_photo_url')
    op.drop_column('employees', 'birthday_visibility')
