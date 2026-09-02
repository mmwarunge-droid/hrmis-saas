from app.extensions import db
from app.models import Employee, User


USER_EMAIL_CONFLICT_MESSAGE = (
    'An account with this email address already exists on the platform. '
    'Please use a different email address or review the existing employee record.'
)

EMPLOYEE_EMAIL_CONFLICT_MESSAGE = (
    'An employee or user with this email address already exists. '
    'Please use a different email address or review the existing employee record.'
)


class EmailAlreadyRegisteredError(ValueError):
    def __init__(self, message=USER_EMAIL_CONFLICT_MESSAGE):
        super().__init__(message)
        self.code = 'EMAIL_ALREADY_REGISTERED'
        self.status_code = 409


def normalize_email_address(value: str) -> str:
    return value.strip().lower()


def normalized_email_expression(column):
    return db.func.lower(db.func.trim(column))


def find_user_by_normalized_email(email, *, exclude_user_id=None):
    normalized = normalize_email_address(email)
    query = User.query.filter(
        normalized_email_expression(User.email) == normalized,
    )
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first()


def find_employee_by_normalized_email(
    tenant_id,
    email,
    *,
    exclude_employee_id=None,
):
    normalized = normalize_email_address(email)
    query = Employee.query.filter(
        Employee.tenant_id == tenant_id,
        normalized_email_expression(Employee.email) == normalized,
    )
    if exclude_employee_id is not None:
        query = query.filter(Employee.id != exclude_employee_id)
    return query.first()


def find_any_employee_by_normalized_email(
    email,
    *,
    exclude_employee_id=None,
):
    normalized = normalize_email_address(email)
    query = Employee.query.filter(
        normalized_email_expression(Employee.email) == normalized,
    )
    if exclude_employee_id is not None:
        query = query.filter(Employee.id != exclude_employee_id)
    return query.first()


def ensure_user_email_available(email):
    normalized = normalize_email_address(email)
    if find_user_by_normalized_email(normalized):
        raise EmailAlreadyRegisteredError(USER_EMAIL_CONFLICT_MESSAGE)
    return normalized


def ensure_user_registration_email_available(email, _tenant_id=None):
    normalized = ensure_user_email_available(email)
    if find_any_employee_by_normalized_email(normalized):
        raise EmailAlreadyRegisteredError(EMPLOYEE_EMAIL_CONFLICT_MESSAGE)
    return normalized


def ensure_access_identity_email_available(email, employee_id):
    normalized = ensure_user_email_available(email)
    if find_any_employee_by_normalized_email(
        normalized,
        exclude_employee_id=employee_id,
    ):
        raise EmailAlreadyRegisteredError(EMPLOYEE_EMAIL_CONFLICT_MESSAGE)
    return normalized


def ensure_employee_email_available(
    tenant_id,
    email,
    *,
    linked_user_id=None,
    exclude_employee_id=None,
):
    normalized = normalize_email_address(email)

    if find_employee_by_normalized_email(
        tenant_id,
        normalized,
        exclude_employee_id=exclude_employee_id,
    ):
        raise EmailAlreadyRegisteredError(EMPLOYEE_EMAIL_CONFLICT_MESSAGE)

    if find_user_by_normalized_email(
        normalized,
        exclude_user_id=linked_user_id,
    ):
        raise EmailAlreadyRegisteredError(EMPLOYEE_EMAIL_CONFLICT_MESSAGE)

    return normalized
