"""add indexes and analytics constraints

Revision ID: 002_add_indexes_and_constraints
Revises: 001_initial_schema
Create Date: 2026-05-17
"""
from alembic import op

revision = '002_add_indexes_and_constraints'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_users_tenant_active', 'users', ['tenant_id', 'is_active'])
    op.execute('CREATE INDEX IF NOT EXISTS ix_users_email_lower ON users (lower(email))')
    op.create_index('ix_departments_tenant_deleted', 'departments', ['tenant_id', 'deleted_at'])
    op.create_index('ix_employees_tenant_deleted_status', 'employees', ['tenant_id', 'deleted_at', 'employment_status'])
    op.create_index('ix_employees_tenant_department', 'employees', ['tenant_id', 'department_id'])
    op.create_index('ix_employees_tenant_manager', 'employees', ['tenant_id', 'manager_id'])
    op.create_index('ix_documents_tenant_type_status', 'documents', ['tenant_id', 'document_type', 'status'])
    op.create_index('ix_documents_tenant_expiry', 'documents', ['tenant_id', 'expiry_date'])
    op.create_index('ix_leave_requests_tenant_status_dates', 'leave_requests', ['tenant_id', 'status', 'start_date', 'end_date'])
    op.create_index('ix_attendance_tenant_work_date', 'attendance_records', ['tenant_id', 'work_date'])
    op.create_index('ix_onboarding_assignments_tenant_status_due', 'employee_onboarding_tasks', ['tenant_id', 'status', 'due_date'])
    op.create_index('ix_audit_logs_tenant_entity_created', 'audit_logs', ['tenant_id', 'entity_type', 'created_at'])
    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'])
    op.create_index('ix_notifications_user_read', 'notifications', ['user_id', 'read_at'])
    op.execute("CREATE INDEX IF NOT EXISTS ix_employees_search_name_email ON employees USING gin (to_tsvector('simple', coalesce(first_name,'') || ' ' || coalesce(last_name,'') || ' ' || coalesce(email,'') || ' ' || coalesce(employee_number,'')))")


def downgrade():
    op.execute('DROP INDEX IF EXISTS ix_employees_search_name_email')
    op.execute('DROP INDEX IF EXISTS ix_users_email_lower')
    for name, table in [
        ('ix_notifications_user_read','notifications'), ('ix_audit_logs_action_created','audit_logs'), ('ix_audit_logs_tenant_entity_created','audit_logs'),
        ('ix_onboarding_assignments_tenant_status_due','employee_onboarding_tasks'), ('ix_attendance_tenant_work_date','attendance_records'),
        ('ix_leave_requests_tenant_status_dates','leave_requests'), ('ix_documents_tenant_expiry','documents'), ('ix_documents_tenant_type_status','documents'),
        ('ix_employees_tenant_manager','employees'), ('ix_employees_tenant_department','employees'), ('ix_employees_tenant_deleted_status','employees'),
        ('ix_departments_tenant_deleted','departments'), ('ix_users_tenant_active','users'),
    ]:
        op.drop_index(name, table_name=table)
