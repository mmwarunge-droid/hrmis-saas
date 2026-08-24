from datetime import date, timedelta

from sqlalchemy import func

from app.extensions import db
from app.models import AccountToken, Department, Employee, JobHistory, Tenant, User
from app.models.base import utcnow
from app.services.account_recovery_service import (
    ensure_identity_email_available,
    issue_account_token,
    normalize_email_address,
    send_account_invitation_email,
    send_email_verification_email,
)
from app.services.audit_service import log_event


class DuplicateJobTitleConfirmationRequired(Exception):
    def __init__(self, job_title):
        self.job_title = job_title
        super().__init__(
            'This organization already has an employee assigned '
            f'to the job title {job_title}. '
            'Are you sure you want to continue?'
        )


def _normalize_job_title(value):
    if value is None:
        return None
    return value.strip()


def _job_title_key(value):
    normalized = _normalize_job_title(value)
    if not normalized:
        return None
    return normalized.lower()


def _warning_title_is_configured(tenant_id, job_title):
    job_title_key = _job_title_key(job_title)
    if not job_title_key:
        return False

    tenant = db.session.get(Tenant, tenant_id)
    if tenant is None:
        return False

    configured_keys = {
        key
        for title in (tenant.duplicate_job_title_warning_titles or [])
        if (key := _job_title_key(title))
    }
    return job_title_key in configured_keys


JOB_TITLE_OCCUPYING_STATUSES = {'active', 'probation'}


def _job_title_is_occupied_by_status(employment_status):
    return employment_status in JOB_TITLE_OCCUPYING_STATUSES


def _duplicate_job_title_exists(
    tenant_id,
    job_title,
    *,
    exclude_employee_id=None,
):
    normalized = _normalize_job_title(job_title)
    if not normalized:
        return False

    query = Employee.query.filter(
        Employee.tenant_id == tenant_id,
        Employee.deleted_at.is_(None),
        Employee.employment_status.in_(JOB_TITLE_OCCUPYING_STATUSES),
        func.lower(func.trim(Employee.job_title)) == normalized.lower(),
    )

    if exclude_employee_id is not None:
        query = query.filter(Employee.id != exclude_employee_id)

    return db.session.query(query.exists()).scalar()


def _require_duplicate_job_title_confirmation(
    tenant_id,
    job_title,
    *,
    confirmed=False,
    exclude_employee_id=None,
    employment_status='active',
):
    if confirmed or not _job_title_is_occupied_by_status(employment_status):
        return

    normalized = _normalize_job_title(job_title)
    if not _warning_title_is_configured(tenant_id, normalized):
        return

    if _duplicate_job_title_exists(
        tenant_id,
        normalized,
        exclude_employee_id=exclude_employee_id,
    ):
        raise DuplicateJobTitleConfirmationRequired(normalized)


def _assert_tenant_fk(model, object_id, tenant_id, field_name):
    if not object_id:
        return None

    query = model.query.filter_by(id=object_id, tenant_id=tenant_id)
    if hasattr(model, 'deleted_at'):
        query = query.filter(model.deleted_at.is_(None))

    obj = query.first()
    if not obj:
        raise ValueError(f'{field_name} is invalid for this tenant')
    return obj


def _assert_valid_manager(employee, manager_id, tenant_id):
    if not manager_id:
        return

    manager = _assert_tenant_fk(Employee, manager_id, tenant_id, 'manager_id')
    visited = set()
    current = manager

    while current is not None:
        current_id = str(current.id)
        if current_id in visited:
            raise ValueError('The reporting line already contains a cycle')
        visited.add(current_id)

        if employee is not None and current_id == str(employee.id):
            if current_id == str(manager.id):
                raise ValueError('An employee cannot report to themselves')
            raise ValueError('Manager assignment would create a reporting cycle')

        if not current.manager_id:
            break

        current = Employee.query.filter_by(
            id=current.manager_id,
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()


def _validate_effective_date(employee, effective_date):
    resolved = effective_date or date.today()
    if resolved > date.today():
        raise ValueError('Effective date cannot be in the future')
    if employee.hire_date and resolved < employee.hire_date:
        raise ValueError(f'Effective date cannot be before {employee.full_name}\'s hire date')
    return resolved


def _clear_department_head_if_departing(employee, old_department_id, new_department_id):
    if not old_department_id or str(old_department_id) == str(new_department_id):
        return

    Department.query.filter(
        Department.id == old_department_id,
        Department.tenant_id == employee.tenant_id,
        Department.head_employee_id == employee.id,
        Department.deleted_at.is_(None),
    ).update({'head_employee_id': None}, synchronize_session=False)


def _record_job_change(employee, effective_date, reason):
    effective_date = _validate_effective_date(employee, effective_date)
    job_title = employee.job_title or 'Unassigned'
    reason = ((reason or '').strip() or 'Profile update')[:255]

    open_entries = (
        JobHistory.query.filter_by(
            tenant_id=employee.tenant_id,
            employee_id=employee.id,
            end_date=None,
        )
        .order_by(JobHistory.start_date.desc(), JobHistory.created_at.desc())
        .all()
    )
    current = open_entries[0] if open_entries else None

    if current and current.start_date > effective_date:
        raise ValueError('Effective date cannot be earlier than the current job history entry')

    close_date = effective_date - timedelta(days=1)
    for stale in open_entries[1:]:
        stale.end_date = max(stale.start_date, close_date)

    if current and current.start_date == effective_date:
        current.job_title = job_title
        current.department_id = employee.department_id
        current.manager_id = employee.manager_id
        current.reason = reason
        return current

    if current:
        current.end_date = close_date

    history = JobHistory(
        tenant_id=employee.tenant_id,
        employee_id=employee.id,
        job_title=job_title,
        department_id=employee.department_id,
        manager_id=employee.manager_id,
        start_date=effective_date,
        reason=reason,
    )
    db.session.add(history)
    return history


def create_employee(payload, tenant_id, commit: bool = True):
    payload = dict(payload)
    confirm_duplicate_job_title = payload.pop(
        'confirm_duplicate_job_title',
        False,
    )

    if 'job_title' in payload:
        payload['job_title'] = _normalize_job_title(payload.get('job_title'))

    _assert_tenant_fk(User, payload.get('user_id'), tenant_id, 'user_id')
    _assert_tenant_fk(Department, payload.get('department_id'), tenant_id, 'department_id')
    _assert_valid_manager(None, payload.get('manager_id'), tenant_id)

    _require_duplicate_job_title_confirmation(
        tenant_id,
        payload.get('job_title'),
        confirmed=confirm_duplicate_job_title,
        employment_status=payload.get('employment_status', 'active'),
    )

    employee = Employee(tenant_id=tenant_id, **payload)
    db.session.add(employee)
    db.session.flush()

    _record_job_change(employee, employee.hire_date, 'Initial hire')

    log_event('employee.create', 'Employee', employee.id, tenant_id=tenant_id)
    if commit:
        db.session.commit()
    return employee


def _consume_active_account_tokens(user):
    now = utcnow()
    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.consumed_at.is_(None),
    ).update(
        {AccountToken.consumed_at: now},
        synchronize_session=False,
    )
    return now


def _update_employee_email(employee, requested_email):
    normalized = normalize_email_address(requested_email)
    user = employee.user

    if not user:
        employee.email = normalized
        return {
            'mode': 'employee_only',
            'requested_email': normalized,
        }

    current_identity_email = normalize_email_address(user.email)

    # No authentication identity change is required. This also repairs a
    # linked employee record that may already have drifted from User.email.
    if normalized == current_identity_email:
        employee.email = normalized
        return {
            'mode': 'synchronized',
            'requested_email': normalized,
        }

    ensure_identity_email_available(user, normalized)

    # A live invited user cannot authenticate until activation succeeds,
    # so it is safe to move the identity immediately and issue a fresh
    # invitation to the replacement address.
    if user.is_active and user.activation_required:
        old_email = user.email

        user.email = normalized
        employee.email = normalized
        user.email_verified_at = None

        now = _consume_active_account_tokens(user)

        account_token, raw_token = issue_account_token(
            user,
            AccountToken.PURPOSE_ACCOUNT_INVITE,
        )
        send_account_invitation_email(user, raw_token)
        user.invitation_sent_at = now

        log_event(
            'employee.identity_email_changed',
            'Employee',
            employee.id,
            tenant_id=employee.tenant_id,
            metadata={
                'user_id': str(user.id),
                'old_email': old_email,
                'new_email': normalized,
                'lifecycle': 'invited',
                'delivery': 'invitation',
                'account_token_id': str(account_token.id),
            },
        )

        return {
            'mode': 'invitation_reissued',
            'requested_email': normalized,
        }

    # Active/suspended established identities retain their current login
    # email until ownership of the proposed address is proven.
    account_token, raw_token = issue_account_token(
        user,
        AccountToken.PURPOSE_EMAIL_VERIFICATION,
        target_email=normalized,
    )
    send_email_verification_email(
        user,
        raw_token,
        to_address=normalized,
    )

    log_event(
        'employee.identity_email_change_requested',
        'Employee',
        employee.id,
        tenant_id=employee.tenant_id,
        metadata={
            'user_id': str(user.id),
            'current_email': user.email,
            'requested_email': normalized,
            'account_token_id': str(account_token.id),
        },
    )

    return {
        'mode': 'verification_pending',
        'requested_email': normalized,
    }


def update_employee(employee, payload, commit: bool = True):
    payload = dict(payload)
    tenant_id = employee.tenant_id
    effective_date = payload.pop('change_effective_date', None)
    change_reason = payload.pop('change_reason', None)
    requested_email = payload.pop('email', None)
    confirm_duplicate_job_title = payload.pop(
        'confirm_duplicate_job_title',
        False,
    )

    if 'job_title' in payload:
        payload['job_title'] = _normalize_job_title(payload.get('job_title'))

    if 'user_id' in payload:
        _assert_tenant_fk(User, payload.get('user_id'), tenant_id, 'user_id')
    if 'department_id' in payload:
        _assert_tenant_fk(
            Department,
            payload.get('department_id'),
            tenant_id,
            'department_id',
        )
    if 'manager_id' in payload:
        _assert_valid_manager(
            employee,
            payload.get('manager_id'),
            tenant_id,
        )

    proposed_job_title = payload.get('job_title', employee.job_title)
    proposed_employment_status = payload.get(
        'employment_status',
        employee.employment_status,
    )
    job_title_changed = (
        'job_title' in payload
        and _job_title_key(proposed_job_title)
        != _job_title_key(employee.job_title)
    )
    starts_job_title_occupancy = (
        not _job_title_is_occupied_by_status(employee.employment_status)
        and _job_title_is_occupied_by_status(proposed_employment_status)
    )

    if job_title_changed or starts_job_title_occupancy:
        _require_duplicate_job_title_confirmation(
            tenant_id,
            proposed_job_title,
            confirmed=confirm_duplicate_job_title,
            exclude_employee_id=employee.id,
            employment_status=proposed_employment_status,
        )

    old_job = (
        employee.job_title,
        employee.department_id,
        employee.manager_id,
    )
    old_department_id = employee.department_id
    old_status = employee.employment_status

    email_change = {
        'mode': 'none',
        'requested_email': None,
    }

    for key, value in payload.items():
        if key != 'tenant_id':
            setattr(employee, key, value)

    new_job = (
        employee.job_title,
        employee.department_id,
        employee.manager_id,
    )
    if new_job != old_job:
        _clear_department_head_if_departing(
            employee,
            old_department_id,
            employee.department_id,
        )
        _record_job_change(
            employee,
            effective_date,
            change_reason,
        )

    if (
        old_status != 'terminated'
        and employee.employment_status == 'terminated'
    ):
        Department.query.filter(
            Department.tenant_id == tenant_id,
            Department.head_employee_id == employee.id,
            Department.deleted_at.is_(None),
        ).update(
            {'head_employee_id': None},
            synchronize_session=False,
        )

    # Defer outbound identity email until all ordinary employee mutations
    # and employment-history validation have succeeded. Token issuance
    # flushes the pending transaction before delivery.
    if requested_email is not None:
        email_change = _update_employee_email(
            employee,
            requested_email,
        )

    log_event(
        'employee.update',
        'Employee',
        employee.id,
        tenant_id=tenant_id,
        metadata={
            'job_assignment_changed': new_job != old_job,
            'reason': change_reason,
            'email_change_mode': email_change['mode'],
            'requested_email': email_change['requested_email'],
        },
    )

    if commit:
        db.session.commit()
    return employee


def transfer_employees_department(
    employees,
    department_id,
    effective_date,
    reason,
    tenant_id,
    commit: bool = True,
):
    target_department = _assert_tenant_fk(
        Department,
        department_id,
        tenant_id,
        'department_id',
    )

    changed = []
    for employee in employees:
        if str(employee.tenant_id) != str(tenant_id):
            raise ValueError('Employees can only be transferred within their tenant')
        if employee.deleted_at is not None:
            raise ValueError(f'{employee.full_name} is not an active employee record')
        if str(employee.department_id) == str(department_id):
            continue

        resolved_date = _validate_effective_date(employee, effective_date)
        old_department_id = employee.department_id
        employee.department_id = target_department.id if target_department else None
        _clear_department_head_if_departing(employee, old_department_id, employee.department_id)
        _record_job_change(employee, resolved_date, reason)
        log_event(
            'employee.department_transfer',
            'Employee',
            employee.id,
            tenant_id=tenant_id,
            metadata={
                'from_department_id': str(old_department_id) if old_department_id else None,
                'to_department_id': str(employee.department_id) if employee.department_id else None,
                'effective_date': resolved_date.isoformat(),
                'reason': reason,
            },
        )
        changed.append(employee)

    if commit:
        db.session.commit()
    return changed


def soft_delete_employee(employee):
    employee.soft_delete()
    Department.query.filter(
        Department.tenant_id == employee.tenant_id,
        Department.head_employee_id == employee.id,
        Department.deleted_at.is_(None),
    ).update({'head_employee_id': None}, synchronize_session=False)
    log_event('employee.delete', 'Employee', employee.id, tenant_id=employee.tenant_id)
    db.session.commit()
