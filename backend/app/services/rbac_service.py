from app.extensions import db
from app.models import Permission, Role, RolePermission, UserRole

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



TENANT_ASSIGNABLE_ROLES = {'CLIENT_ADMIN', 'MANAGER', 'EMPLOYEE'}


def validate_role_assignment(actor, role_names, tenant_id=None):
    """Prevent tenant-scoped administrators from granting platform-wide roles."""
    requested = set(role_names)
    if actor is None or actor.has_role('SUPER_ADMIN'):
        return

    forbidden = requested - TENANT_ASSIGNABLE_ROLES
    if forbidden:
        raise ValueError(f'Not authorized to assign role(s): {", ".join(sorted(forbidden))}')
    if str(actor.tenant_id) != str(tenant_id):
        raise ValueError('Users can only be managed within your tenant')


ROLE_PERMISSIONS = {
    'SUPER_ADMIN': list(PERMISSIONS.keys()),
    'HR_CONSULTANT': ['tenant:read','user:create','user:read','user:update','employee:create','employee:read','employee:update','employee:delete','document:upload','document:read','document:approve','leave:create','leave:approve','attendance:read','onboarding:create','onboarding:assign','dashboard:read'],
    'CLIENT_ADMIN': ['user:create','user:read','user:update','employee:create','employee:read','employee:update','employee:delete','document:upload','document:read','document:approve','leave:create','leave:approve','attendance:read','onboarding:create','onboarding:assign','dashboard:read'],
    'MANAGER': ['employee:read','document:read','leave:create','leave:approve','attendance:read','onboarding:assign','dashboard:read'],
    'EMPLOYEE': ['employee:read','document:read','leave:create','attendance:write','onboarding:assign'],
}


def seed_roles_permissions(commit=True):
    permissions = {}
    for code, description in PERMISSIONS.items():
        permission = Permission.query.filter_by(code=code).first()
        if not permission:
            permission = Permission(code=code, description=description)
            db.session.add(permission)
        permissions[code] = permission
    db.session.flush()

    for role_name, codes in ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            role = Role(name=role_name, description=f'{role_name} system role')
            db.session.add(role)
            db.session.flush()
        existing = {link.permission.code for link in role.permission_links}
        for code in codes:
            if code not in existing:
                db.session.add(RolePermission(role_id=role.id, permission_id=permissions[code].id))
    if commit:
        db.session.commit()


def set_user_roles(user, role_names, assigned_by_id=None, commit=False):
    roles = Role.query.filter(Role.name.in_(role_names)).all()
    found = {role.name for role in roles}
    missing = set(role_names) - found
    if missing:
        raise ValueError(f'Unknown role(s): {", ".join(sorted(missing))}')
    user.role_links.clear()
    db.session.flush()
    for role in roles:
        db.session.add(UserRole(user_id=user.id, role_id=role.id, tenant_id=user.tenant_id, assigned_by_id=assigned_by_id))
    if commit:
        db.session.commit()
