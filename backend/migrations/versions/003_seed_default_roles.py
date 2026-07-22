"""seed default roles and permissions

Revision ID: 003_seed_default_roles
Revises: 002_add_indexes_and_constraints
Create Date: 2026-05-17
"""
from alembic import op

revision = '003_seed_default_roles'
down_revision = '002_add_indexes_and_constraints'
branch_labels = None
depends_on = None

PERMISSIONS = {
    'tenant:create': 'Create client tenants',
    'tenant:read': 'Read client tenants',
    'tenant:update': 'Update client tenants',
    'user:create': 'Create users',
    'user:read': 'Read users',
    'user:update': 'Update users',
    'employee:create': 'Create employees',
    'employee:read': 'Read employees',
    'employee:update': 'Update employees',
    'employee:delete': 'Soft-delete employees',
    'document:upload': 'Upload documents',
    'document:read': 'Read document metadata and download permitted documents',
    'document:approve': 'Approve or classify documents',
    'leave:create': 'Create leave requests',
    'leave:approve': 'Approve/reject leave requests',
    'attendance:read': 'Read attendance records',
    'attendance:write': 'Create attendance records',
    'onboarding:create': 'Create onboarding templates',
    'onboarding:assign': 'Assign onboarding templates',
    'dashboard:read': 'Read dashboard analytics',
}

ROLE_PERMISSIONS = {
    'SUPER_ADMIN': list(PERMISSIONS.keys()),
    'HR_CONSULTANT': ['tenant:read','user:create','user:read','user:update','employee:create','employee:read','employee:update','employee:delete','document:upload','document:read','document:approve','leave:create','leave:approve','attendance:read','onboarding:create','onboarding:assign','dashboard:read'],
    'CLIENT_ADMIN': ['user:create','user:read','user:update','employee:create','employee:read','employee:update','document:upload','document:read','document:approve','leave:create','leave:approve','attendance:read','onboarding:create','onboarding:assign','dashboard:read'],
    'MANAGER': ['employee:read','document:read','leave:create','leave:approve','attendance:read','onboarding:assign','dashboard:read'],
    'EMPLOYEE': ['employee:read','document:read','leave:create','attendance:write','onboarding:assign'],
}


def upgrade():
    for code, description in PERMISSIONS.items():
        op.execute(f"""
        INSERT INTO permissions (code, description)
        VALUES ('{code}', '{description.replace("'", "''")}')
        ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description, updated_at = CURRENT_TIMESTAMP;
        """)

    for role, codes in ROLE_PERMISSIONS.items():
        op.execute(f"""
        INSERT INTO roles (name, description, is_system)
        VALUES ('{role}', '{role} system role', true)
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, is_system = true, updated_at = CURRENT_TIMESTAMP;
        """)
        for code in codes:
            op.execute(f"""
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT r.id, p.id FROM roles r, permissions p
            WHERE r.name = '{role}' AND p.code = '{code}'
            ON CONFLICT (role_id, permission_id) DO NOTHING;
            """)


def downgrade():
    op.execute('DELETE FROM role_permissions')
    op.execute("DELETE FROM roles WHERE name IN ('SUPER_ADMIN','HR_CONSULTANT','CLIENT_ADMIN','MANAGER','EMPLOYEE')")
    op.execute("DELETE FROM permissions WHERE code IN (" + ','.join([f"'{code}'" for code in PERMISSIONS.keys()]) + ")")
