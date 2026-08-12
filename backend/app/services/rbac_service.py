from app.extensions import db
from app.models import Permission, Role, RolePermission, UserRole


PERMISSIONS = {
    'tenant:create': 'Create organizations',
    'tenant:read': 'Read organization records',
    'tenant:update': 'Update organization records',
    'user:create': 'Create user accounts',
    'user:read': 'Read user accounts',
    'user:update': 'Update user accounts and roles',
    'employee:create': 'Create employee records',
    'employee:read': 'Read employee records',
    'employee:update': 'Update employee records',
    'employee:delete': 'Archive employee records',
    'document:upload': 'Upload documents',
    'document:read': 'Read documents',
    'document:approve': 'Approve documents and manage signatures',
    'leave:create': 'Create leave requests',
    'leave:approve': 'Approve/reject leave requests',
    'leave:ledger': 'Read leave allocation ledger entries',
    'leave:adjust': 'Adjust leave balances and run allocations',
    'attendance:read': 'Read attendance records',
    'attendance:write': 'Record attendance',
    'onboarding:create': 'Create onboarding templates',
    'onboarding:self': 'Access personal onboarding work',
    'onboarding:assign': 'Assign and administer onboarding work',
    'dashboard:read': 'Read dashboard information',
    'goal:read': 'Read goals and KPI progress',
    'goal:manage': 'Create and manage goals',
    'goal:checkin': 'Record goal progress check-ins',
    'security:mfa_policy': (
        'Configure organization MFA policy and review compliance'
    ),
    'security:mfa_reset': 'Reset another user MFA enrollment',
}

TENANT_ASSIGNABLE_ROLES = {'MANAGER', 'EMPLOYEE'}

ROLE_PERMISSIONS = {
    'SUPER_ADMIN': list(PERMISSIONS.keys()),
    'ORGANIZATION_OWNER': [
        'tenant:read',
        'user:read',
        'employee:read',
        'document:read',
        'document:approve',
        'leave:create',
        'leave:approve',
        'leave:ledger',
        'leave:adjust',
        'attendance:read',
        'dashboard:read',
        'goal:read',
        'goal:manage',
        'goal:checkin',
        'security:mfa_policy',
        'security:mfa_reset',
    ],
    'HR_CONSULTANT': [
        'tenant:read',
        'user:create',
        'user:read',
        'user:update',
        'employee:create',
        'employee:read',
        'employee:update',
        'employee:delete',
        'document:upload',
        'document:read',
        'document:approve',
        'leave:create',
        'leave:approve',
        'leave:ledger',
        'leave:adjust',
        'attendance:read',
        'onboarding:create',
        'onboarding:assign',
        'dashboard:read',
        'goal:read',
        'goal:manage',
        'goal:checkin',
    ],
    'CLIENT_ADMIN': [
        'user:create',
        'user:read',
        'user:update',
        'employee:create',
        'employee:read',
        'employee:update',
        'employee:delete',
        'document:upload',
        'document:read',
        'document:approve',
        'leave:create',
        'leave:approve',
        'leave:ledger',
        'leave:adjust',
        'attendance:read',
        'onboarding:create',
        'onboarding:assign',
        'dashboard:read',
        'goal:read',
        'goal:manage',
        'goal:checkin',
        'security:mfa_policy',
        'security:mfa_reset',
    ],
    'MANAGER': [
        'employee:read',
        'document:read',
        'leave:create',
        'leave:approve',
        'leave:ledger',
        'attendance:read',
        'onboarding:self',
        'onboarding:assign',
        'dashboard:read',
        'goal:read',
        'goal:manage',
        'goal:checkin',
    ],
    'EMPLOYEE': [
        'employee:read',
        'document:read',
        'leave:create',
        'leave:ledger',
        'attendance:write',
        'onboarding:self',
        'dashboard:read',
        'goal:read',
        'goal:checkin',
    ],
}


def validate_role_assignment(actor, roles, tenant_id):
    requested = set(roles or [])
    unknown = requested - set(ROLE_PERMISSIONS)
    if unknown:
        raise ValueError(
            'Unknown role assignment: '
            + ', '.join(sorted(unknown))
        )

    if actor is None:
        return

    if actor.has_role('SUPER_ADMIN'):
        if tenant_id and 'SUPER_ADMIN' in requested:
            raise ValueError(
                'SUPER_ADMIN is reserved for platform accounts'
            )
        if not tenant_id and requested != {'SUPER_ADMIN'}:
            raise ValueError(
                'Platform accounts must use the SUPER_ADMIN role'
            )
        return

    if not tenant_id or str(actor.tenant_id) != str(tenant_id):
        raise ValueError(
            'Roles can only be assigned within your organization'
        )

    forbidden = requested - TENANT_ASSIGNABLE_ROLES
    if forbidden:
        raise ValueError(
            'Organization administrators cannot assign privileged roles: '
            + ', '.join(sorted(forbidden))
        )


def seed_roles_permissions(commit: bool = True):
    permissions = {}
    for code, description in PERMISSIONS.items():
        permission = Permission.query.filter_by(code=code).first()
        if permission is None:
            permission = Permission(
                code=code,
                description=description,
            )
            db.session.add(permission)
            db.session.flush()
        elif permission.description != description:
            permission.description = description
        permissions[code] = permission

    for role_name, permission_codes in ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(
                name=role_name,
                description=role_name.replace('_', ' ').title(),
                is_system=True,
            )
            db.session.add(role)
            db.session.flush()

        existing = {
            link.permission.code: link
            for link in role.permission_links
        }
        expected = set(permission_codes)

        for code in expected - set(existing):
            db.session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=permissions[code].id,
                )
            )

        for code in set(existing) - expected:
            db.session.delete(existing[code])

    if commit:
        db.session.commit()


def set_user_roles(
    user,
    role_names,
    assigned_by_id=None,
    commit: bool = True,
):
    requested = list(dict.fromkeys(role_names or []))
    if not requested:
        raise ValueError('At least one role is required')

    seed_roles_permissions(commit=False)
    roles = Role.query.filter(Role.name.in_(requested)).all()
    found = {role.name for role in roles}
    missing = set(requested) - found
    if missing:
        raise ValueError(
            'Unknown role assignment: '
            + ', '.join(sorted(missing))
        )

    UserRole.query.filter_by(user_id=user.id).delete(
        synchronize_session=False,
    )
    for role in roles:
        db.session.add(
            UserRole(
                tenant_id=user.tenant_id,
                user_id=user.id,
                role_id=role.id,
                assigned_by_id=assigned_by_id,
            )
        )

    if commit:
        db.session.commit()
