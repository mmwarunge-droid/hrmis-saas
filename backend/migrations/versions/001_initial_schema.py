"""initial PostgreSQL HRMIS schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB


def uuid_col(name='id', primary_key=False, nullable=True, fk=None, ondelete=None, index=False):
    args = []
    if fk:
        args.append(sa.ForeignKey(fk, ondelete=ondelete))
    return sa.Column(name, UUID, *args, primary_key=primary_key, nullable=nullable, server_default=sa.text('gen_random_uuid()') if primary_key else None, index=index)


def ts_cols():
    return [
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    ]


def soft_delete_col():
    return sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True)


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS pgcrypto')

    op.create_table('tenants',
        uuid_col(primary_key=True, nullable=False),
        sa.Column('name', sa.String(160), nullable=False),
        sa.Column('slug', sa.String(120), nullable=False),
        sa.Column('legal_name', sa.String(220)),
        sa.Column('country', sa.String(80)),
        sa.Column('industry', sa.String(120)),
        sa.Column('status', sa.String(30), nullable=False, server_default='active'),
        sa.Column('billing_plan', sa.String(60), nullable=False, server_default='mvp'),
        sa.Column('compliance_region', sa.String(80)),
        soft_delete_col(), *ts_cols(),
        sa.CheckConstraint("status IN ('active','suspended','archived')", name='ck_tenants_status'),
        sa.UniqueConstraint('name', name='uq_tenants_name'),
        sa.UniqueConstraint('slug', name='uq_tenants_slug'))

    op.create_table('permissions',
        uuid_col(primary_key=True, nullable=False),
        sa.Column('code', sa.String(120), nullable=False),
        sa.Column('description', sa.String(255)), *ts_cols(),
        sa.UniqueConstraint('code', name='uq_permissions_code'))

    op.create_table('roles',
        uuid_col(primary_key=True, nullable=False),
        sa.Column('name', sa.String(60), nullable=False),
        sa.Column('description', sa.String(255)),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('true')), *ts_cols(),
        sa.UniqueConstraint('name', name='uq_roles_name'))

    op.create_table('role_permissions',
        uuid_col(primary_key=True, nullable=False),
        uuid_col('role_id', fk='roles.id', ondelete='CASCADE', nullable=False),
        uuid_col('permission_id', fk='permissions.id', ondelete='CASCADE', nullable=False), *ts_cols(),
        sa.UniqueConstraint('role_id', 'permission_id', name='uq_role_permission'))

    op.create_table('users',
        uuid_col(primary_key=True, nullable=False),
        uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('first_name', sa.String(120), nullable=False),
        sa.Column('last_name', sa.String(120), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_login_at', sa.DateTime(timezone=True)),
        soft_delete_col(), *ts_cols(),
        sa.UniqueConstraint('email', name='uq_users_email'))

    op.create_table('user_roles',
        uuid_col(primary_key=True, nullable=False),
        uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=True),
        uuid_col('user_id', fk='users.id', ondelete='CASCADE', nullable=False),
        uuid_col('role_id', fk='roles.id', ondelete='CASCADE', nullable=False),
        uuid_col('assigned_by_id', fk='users.id', ondelete='SET NULL', nullable=True), *ts_cols(),
        sa.UniqueConstraint('user_id', 'role_id', name='uq_user_role'))

    op.create_table('departments',
        uuid_col(primary_key=True, nullable=False),
        uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        sa.Column('name', sa.String(140), nullable=False),
        sa.Column('code', sa.String(40)),
        uuid_col('parent_department_id', fk='departments.id', ondelete='SET NULL', nullable=True),
        soft_delete_col(), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_departments_tenant_name'),
        sa.UniqueConstraint('tenant_id', 'code', name='uq_departments_tenant_code'))

    op.create_table('employees',
        uuid_col(primary_key=True, nullable=False),
        uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('user_id', fk='users.id', ondelete='SET NULL', nullable=True),
        sa.Column('employee_number', sa.String(80), nullable=False),
        sa.Column('first_name', sa.String(120), nullable=False),
        sa.Column('last_name', sa.String(120), nullable=False),
        sa.Column('preferred_name', sa.String(120)),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('phone', sa.String(60)),
        sa.Column('date_of_birth', sa.Date()),
        sa.Column('national_identifier_last4', sa.String(12)),
        sa.Column('hire_date', sa.Date(), nullable=False),
        sa.Column('termination_date', sa.Date()),
        sa.Column('employment_status', sa.String(40), nullable=False, server_default='active'),
        sa.Column('employment_type', sa.String(60), nullable=False, server_default='full_time'),
        sa.Column('job_title', sa.String(160)),
        uuid_col('department_id', fk='departments.id', ondelete='SET NULL', nullable=True),
        uuid_col('manager_id', fk='employees.id', ondelete='SET NULL', nullable=True),
        sa.Column('work_location', sa.String(160)),
        sa.Column('address', sa.Text()),
        sa.Column('external_hris_id', sa.String(120)),
        soft_delete_col(), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'employee_number', name='uq_employees_tenant_employee_number'),
        sa.UniqueConstraint('tenant_id', 'email', name='uq_employees_tenant_email'),
        sa.CheckConstraint("employment_status IN ('active','probation','suspended','terminated')", name='ck_employees_status'),
        sa.CheckConstraint("employment_type IN ('full_time','part_time','contractor','intern','temporary')", name='ck_employees_type'))

    op.create_table('emergency_contacts',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False),
        sa.Column('name', sa.String(160), nullable=False), sa.Column('relationship', sa.String(80), nullable=False),
        sa.Column('phone', sa.String(60), nullable=False), sa.Column('email', sa.String(255)),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default=sa.text('false')), *ts_cols())

    op.create_table('job_histories',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False),
        sa.Column('job_title', sa.String(160), nullable=False),
        uuid_col('department_id', fk='departments.id', ondelete='SET NULL', nullable=True),
        uuid_col('manager_id', fk='employees.id', ondelete='SET NULL', nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date()),
        sa.Column('reason', sa.String(255)), sa.Column('compensation_band', sa.String(80)), *ts_cols(),
        sa.CheckConstraint('end_date IS NULL OR end_date >= start_date', name='ck_job_history_date_range'))

    op.create_table('documents',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('employee_id', fk='employees.id', ondelete='SET NULL', nullable=True),
        uuid_col('uploaded_by_id', fk='users.id', ondelete='SET NULL', nullable=True),
        sa.Column('title', sa.String(220), nullable=False), sa.Column('document_type', sa.String(80), nullable=False),
        sa.Column('original_filename', sa.String(255), nullable=False), sa.Column('stored_filename', sa.String(255), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False), sa.Column('mime_type', sa.String(120)), sa.Column('size_bytes', sa.Integer()),
        sa.Column('checksum_sha256', sa.String(64)), sa.Column('expiry_date', sa.Date()), sa.Column('issued_date', sa.Date()),
        sa.Column('signature_status', sa.String(40), nullable=False, server_default='not_required'),
        sa.Column('access_level', sa.String(40), nullable=False, server_default='hr_only'),
        sa.Column('status', sa.String(40), nullable=False, server_default='active'), sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        soft_delete_col(), *ts_cols(),
        sa.UniqueConstraint('stored_filename', name='uq_documents_stored_filename'),
        sa.CheckConstraint("signature_status IN ('not_required','pending','signed','declined','expired')", name='ck_documents_signature_status'),
        sa.CheckConstraint("access_level IN ('employee','manager','hr_only','company_admin')", name='ck_documents_access_level'),
        sa.CheckConstraint("status IN ('active','archived','expired','pending_review')", name='ck_documents_status'))

    op.create_table('leave_types',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('annual_entitlement_days', sa.Numeric(6,2), nullable=False, server_default='0'),
        sa.Column('accrual_method', sa.String(40), nullable=False, server_default='annual'), sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')), sa.Column('carryover_allowed', sa.Boolean(), nullable=False, server_default=sa.text('false')), sa.Column('max_carryover_days', sa.Numeric(6,2), nullable=False, server_default='0'), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'name', name='uq_leave_types_tenant_name'),
        sa.CheckConstraint("accrual_method IN ('annual','monthly','manual','none')", name='ck_leave_types_accrual_method'))

    op.create_table('leave_balances',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False), uuid_col('leave_type_id', fk='leave_types.id', ondelete='CASCADE', nullable=False),
        sa.Column('balance_days', sa.Numeric(8,2), nullable=False, server_default='0'), sa.Column('accrued_days', sa.Numeric(8,2), nullable=False, server_default='0'), sa.Column('used_days', sa.Numeric(8,2), nullable=False, server_default='0'), sa.Column('year', sa.Integer(), nullable=False), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'leave_type_id', 'year', name='uq_leave_balances_tenant_employee_type_year'))

    op.create_table('leave_requests',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False), uuid_col('leave_type_id', fk='leave_types.id', ondelete='RESTRICT', nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False), sa.Column('end_date', sa.Date(), nullable=False), sa.Column('total_days', sa.Numeric(8,2), nullable=False), sa.Column('reason', sa.Text()),
        sa.Column('status', sa.String(40), nullable=False, server_default='pending'), uuid_col('approver_id', fk='users.id', ondelete='SET NULL', nullable=True), sa.Column('decision_notes', sa.Text()), sa.Column('decided_at', sa.DateTime(timezone=True)), *ts_cols(),
        sa.CheckConstraint("status IN ('pending','approved','rejected','cancelled')", name='ck_leave_requests_status'),
        sa.CheckConstraint('end_date >= start_date', name='ck_leave_requests_date_range'), sa.CheckConstraint('total_days > 0', name='ck_leave_requests_total_days_positive'))

    op.create_table('attendance_records',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False), uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False),
        sa.Column('work_date', sa.Date(), nullable=False), sa.Column('check_in_at', sa.DateTime(timezone=True)), sa.Column('check_out_at', sa.DateTime(timezone=True)), sa.Column('source', sa.String(60), nullable=False, server_default='self_service'), sa.Column('notes', sa.Text()), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'work_date', name='uq_attendance_tenant_employee_day'), sa.CheckConstraint('check_out_at IS NULL OR check_in_at IS NULL OR check_out_at >= check_in_at', name='ck_attendance_time_order'))

    op.create_table('onboarding_templates',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False),
        sa.Column('name', sa.String(160), nullable=False), sa.Column('description', sa.Text()), sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')), *ts_cols(), sa.UniqueConstraint('tenant_id', 'name', name='uq_onboarding_templates_tenant_name'))

    op.create_table('onboarding_tasks',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False), uuid_col('template_id', fk='onboarding_templates.id', ondelete='CASCADE', nullable=False),
        sa.Column('title', sa.String(180), nullable=False), sa.Column('description', sa.Text()), sa.Column('assignee_role', sa.String(40), nullable=False, server_default='EMPLOYEE'), sa.Column('due_days_after_start', sa.Integer(), nullable=False, server_default='0'), sa.Column('required', sa.Boolean(), nullable=False, server_default=sa.text('true')), *ts_cols(),
        sa.CheckConstraint("assignee_role IN ('EMPLOYEE','MANAGER','CLIENT_ADMIN','HR_CONSULTANT')", name='ck_onboarding_tasks_assignee_role'))

    op.create_table('employee_onboarding_tasks',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False), uuid_col('employee_id', fk='employees.id', ondelete='CASCADE', nullable=False), uuid_col('task_id', fk='onboarding_tasks.id', ondelete='CASCADE', nullable=False), uuid_col('assigned_to_user_id', fk='users.id', ondelete='SET NULL', nullable=True),
        sa.Column('status', sa.String(40), nullable=False, server_default='pending'), sa.Column('due_date', sa.Date()), sa.Column('completed_at', sa.DateTime(timezone=True)), sa.Column('completion_notes', sa.Text()), *ts_cols(),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'task_id', name='uq_employee_onboarding_task'),
        sa.CheckConstraint("status IN ('pending','in_progress','completed','waived','overdue')", name='ck_employee_onboarding_tasks_status'))

    op.create_table('audit_logs',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=True), uuid_col('actor_user_id', fk='users.id', ondelete='SET NULL', nullable=True),
        sa.Column('action', sa.String(120), nullable=False), sa.Column('entity_type', sa.String(80), nullable=False), sa.Column('entity_id', UUID), sa.Column('ip_address', sa.String(80)), sa.Column('user_agent', sa.String(255)), sa.Column('metadata_json', JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")), *ts_cols())

    op.create_table('notifications',
        uuid_col(primary_key=True, nullable=False), uuid_col('tenant_id', fk='tenants.id', ondelete='CASCADE', nullable=False), uuid_col('user_id', fk='users.id', ondelete='CASCADE', nullable=False),
        sa.Column('title', sa.String(180), nullable=False), sa.Column('body', sa.Text()), sa.Column('notification_type', sa.String(80), nullable=False, server_default='system'), sa.Column('read_at', sa.DateTime(timezone=True)), *ts_cols())


def downgrade():
    for table in ['notifications','audit_logs','employee_onboarding_tasks','onboarding_tasks','onboarding_templates','attendance_records','leave_requests','leave_balances','leave_types','documents','job_histories','emergency_contacts','employees','departments','user_roles','users','role_permissions','roles','permissions','tenants']:
        op.drop_table(table)
