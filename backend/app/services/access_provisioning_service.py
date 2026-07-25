from app.extensions import db
from app.models import Employee, User
from app.services.audit_service import log_event
from app.services.auth_service import register_user
from app.services.rbac_service import validate_role_assignment

ACCESS_ROLES = {'EMPLOYEE', 'MANAGER'}


class AccessProvisioningError(ValueError):
    def __init__(self, code: str, message: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def provision_employee_access(employee: Employee, payload: dict, actor) -> User:
    """Create a tenant-scoped user and link it to an existing employee atomically."""
    if employee.user_id:
        raise AccessProvisioningError(
            'EMPLOYEE_ACCESS_EXISTS',
            'This employee already has a user account',
            409,
        )
    if employee.employment_status == 'terminated':
        raise AccessProvisioningError(
            'EMPLOYEE_NOT_ELIGIBLE',
            'Access cannot be provisioned for a terminated employee',
        )

    roles = payload['roles']
    invalid_roles = set(roles) - ACCESS_ROLES
    if invalid_roles:
        raise AccessProvisioningError(
            'INVALID_ACCESS_ROLE',
            'Existing employees can only be assigned the EMPLOYEE or MANAGER role',
        )

    validate_role_assignment(actor, roles, employee.tenant_id)

    email = employee.email.strip().lower()
    if User.query.filter_by(email=email).first():
        raise AccessProvisioningError(
            'EMAIL_ALREADY_REGISTERED',
            'A user account with this employee email already exists',
            409,
        )

    user = register_user(
        {
            'tenant_id': employee.tenant_id,
            'email': email,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'password': payload['password'],
            'roles': roles,
        },
        actor=actor,
        commit=False,
    )
    employee.user_id = user.id

    log_event('user.create', 'User', user.id, tenant_id=employee.tenant_id)
    log_event(
        'employee.access_provisioned',
        'Employee',
        employee.id,
        tenant_id=employee.tenant_id,
        metadata={
            'user_id': str(user.id),
            'roles': roles,
        },
    )
    db.session.commit()
    return user
