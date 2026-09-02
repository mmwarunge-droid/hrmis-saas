from app.extensions import db
from app.models import AccountToken, Employee, User
from app.models.base import utcnow
from app.services.account_recovery_service import (
    issue_account_token,
    send_account_invitation_email,
)
from app.services.audit_service import log_event
from app.services.auth_service import register_invited_user
from app.services.email_identity_service import (
    EmailAlreadyRegisteredError,
    ensure_access_identity_email_available,
)
from app.services.rbac_service import validate_role_assignment
from app.utils.email import EmailDeliveryError

ACCESS_ROLES = {'EMPLOYEE', 'MANAGER'}


class AccessProvisioningError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def provision_employee_access(
    employee: Employee,
    payload: dict,
    actor,
) -> User:
    """Create invite-only access and link it to an existing employee."""
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

    try:
        email = ensure_access_identity_email_available(
            employee.email,
            employee.id,
        )
    except EmailAlreadyRegisteredError as exc:
        raise AccessProvisioningError(
            exc.code,
            str(exc),
            exc.status_code,
        ) from exc

    user = register_invited_user(
        {
            'tenant_id': employee.tenant_id,
            'email': email,
            'first_name': employee.first_name,
            'last_name': employee.last_name,
            'roles': roles,
        },
        actor=actor,
        commit=False,
    )
    employee.user_id = user.id
    account_token, raw_token = issue_account_token(
        user,
        AccountToken.PURPOSE_ACCOUNT_INVITE,
    )

    log_event(
        'user.invited',
        'AccountToken',
        account_token.id,
        tenant_id=employee.tenant_id,
        actor=actor,
        metadata={'user_id': str(user.id)},
    )
    log_event(
        'user.create',
        'User',
        user.id,
        tenant_id=employee.tenant_id,
    )
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

    try:
        send_account_invitation_email(user, raw_token)
        user.invitation_sent_at = utcnow()
        log_event(
            'user.invitation_sent',
            'User',
            user.id,
            tenant_id=user.tenant_id,
            actor=actor,
            metadata={'account_token_id': str(account_token.id)},
        )
        db.session.commit()
    except EmailDeliveryError:
        db.session.rollback()
        log_event(
            'user.invitation_delivery_failed',
            'User',
            user.id,
            tenant_id=user.tenant_id,
            actor=actor,
            metadata={
                'account_token_id': str(account_token.id),
                'trigger': 'employee_access_provisioning',
            },
        )
        db.session.commit()

    return user
