"""add leave policy setup and owner governance

Revision ID: 014_leave_owner_governance
Revises: 013_qes_evidence_ingestion
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '014_leave_owner_governance'
down_revision = '013_qes_evidence_ingestion'
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column(
        'tenants',
        sa.Column('organization_owner_user_id', UUID, nullable=True),
    )
    op.add_column(
        'tenants',
        sa.Column('leave_alternate_approver_user_id', UUID, nullable=True),
    )
    op.add_column(
        'tenants',
        sa.Column('leave_setup_completed_at', sa.DateTime(), nullable=True),
    )
    op.create_foreign_key(
        'fk_tenants_organization_owner_user_id_users',
        'tenants',
        'users',
        ['organization_owner_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_tenants_leave_alternate_approver_user_id_users',
        'tenants',
        'users',
        ['leave_alternate_approver_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_tenants_organization_owner_user_id',
        'tenants',
        ['organization_owner_user_id'],
    )
    op.create_index(
        'ix_tenants_leave_alternate_approver_user_id',
        'tenants',
        ['leave_alternate_approver_user_id'],
    )

    op.add_column(
        'leave_types',
        sa.Column('code', sa.String(length=80), nullable=True),
    )
    op.add_column(
        'leave_types',
        sa.Column(
            'entitlement_mode',
            sa.String(length=40),
            nullable=False,
            server_default='granted_upfront',
        ),
    )
    op.add_column(
        'leave_types',
        sa.Column(
            'pay_percentage',
            sa.Numeric(5, 2),
            nullable=False,
            server_default='100',
        ),
    )
    op.add_column(
        'leave_types',
        sa.Column(
            'eligibility_after_months',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'leave_types',
        sa.Column(
            'allow_negative_balance',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        'leave_types',
        sa.Column(
            'minimum_notice_days',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'leave_types',
        sa.Column('documentation_after_days', sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        'uq_leave_types_tenant_code',
        'leave_types',
        ['tenant_id', 'code'],
    )
    op.create_check_constraint(
        'ck_leave_types_entitlement_mode',
        'leave_types',
        "entitlement_mode IN ("
        "'accrued','granted_upfront','event_based','unlimited','manual'"
        ")",
    )
    op.create_check_constraint(
        'ck_leave_types_pay_percentage',
        'leave_types',
        'pay_percentage >= 0 AND pay_percentage <= 100',
    )
    op.create_check_constraint(
        'ck_leave_types_eligibility_months',
        'leave_types',
        'eligibility_after_months >= 0',
    )
    op.create_check_constraint(
        'ck_leave_types_minimum_notice_days',
        'leave_types',
        'minimum_notice_days >= 0',
    )
    op.create_check_constraint(
        'ck_leave_types_documentation_after_days',
        'leave_types',
        'documentation_after_days IS NULL '
        'OR documentation_after_days >= 0',
    )

    op.add_column(
        'leave_requests',
        sa.Column('requested_by_user_id', UUID, nullable=True),
    )
    op.add_column(
        'leave_requests',
        sa.Column('required_approver_id', UUID, nullable=True),
    )
    op.add_column(
        'leave_requests',
        sa.Column('approval_route', sa.String(length=80), nullable=True),
    )
    op.create_foreign_key(
        'fk_leave_requests_requested_by_user_id_users',
        'leave_requests',
        'users',
        ['requested_by_user_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'fk_leave_requests_required_approver_id_users',
        'leave_requests',
        'users',
        ['required_approver_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.create_index(
        'ix_leave_requests_requested_by_user_id',
        'leave_requests',
        ['requested_by_user_id'],
    )
    op.create_index(
        'ix_leave_requests_required_approver_id',
        'leave_requests',
        ['required_approver_id'],
    )


def downgrade():
    op.drop_index(
        'ix_leave_requests_required_approver_id',
        table_name='leave_requests',
    )
    op.drop_index(
        'ix_leave_requests_requested_by_user_id',
        table_name='leave_requests',
    )
    op.drop_constraint(
        'fk_leave_requests_required_approver_id_users',
        'leave_requests',
        type_='foreignkey',
    )
    op.drop_constraint(
        'fk_leave_requests_requested_by_user_id_users',
        'leave_requests',
        type_='foreignkey',
    )
    op.drop_column('leave_requests', 'approval_route')
    op.drop_column('leave_requests', 'required_approver_id')
    op.drop_column('leave_requests', 'requested_by_user_id')

    for name in [
        'ck_leave_types_documentation_after_days',
        'ck_leave_types_minimum_notice_days',
        'ck_leave_types_eligibility_months',
        'ck_leave_types_pay_percentage',
        'ck_leave_types_entitlement_mode',
        'uq_leave_types_tenant_code',
    ]:
        op.drop_constraint(name, 'leave_types', type_='check' if name.startswith('ck_') else 'unique')
    op.drop_column('leave_types', 'documentation_after_days')
    op.drop_column('leave_types', 'minimum_notice_days')
    op.drop_column('leave_types', 'allow_negative_balance')
    op.drop_column('leave_types', 'eligibility_after_months')
    op.drop_column('leave_types', 'pay_percentage')
    op.drop_column('leave_types', 'entitlement_mode')
    op.drop_column('leave_types', 'code')

    op.drop_index(
        'ix_tenants_leave_alternate_approver_user_id',
        table_name='tenants',
    )
    op.drop_index(
        'ix_tenants_organization_owner_user_id',
        table_name='tenants',
    )
    op.drop_constraint(
        'fk_tenants_leave_alternate_approver_user_id_users',
        'tenants',
        type_='foreignkey',
    )
    op.drop_constraint(
        'fk_tenants_organization_owner_user_id_users',
        'tenants',
        type_='foreignkey',
    )
    op.drop_column('tenants', 'leave_setup_completed_at')
    op.drop_column('tenants', 'leave_alternate_approver_user_id')
    op.drop_column('tenants', 'organization_owner_user_id')
