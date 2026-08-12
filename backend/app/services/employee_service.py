from datetime import date, timedelta

from app.extensions import db
from app.models import Department, Employee, JobHistory, User
from app.services.audit_service import log_event


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
    _assert_tenant_fk(User, payload.get('user_id'), tenant_id, 'user_id')
    _assert_tenant_fk(Department, payload.get('department_id'), tenant_id, 'department_id')
    _assert_valid_manager(None, payload.get('manager_id'), tenant_id)

    employee = Employee(tenant_id=tenant_id, **payload)
    db.session.add(employee)
    db.session.flush()

    _record_job_change(employee, employee.hire_date, 'Initial hire')

    log_event('employee.create', 'Employee', employee.id, tenant_id=tenant_id)
    if commit:
        db.session.commit()
    return employee


def update_employee(employee, payload, commit: bool = True):
    tenant_id = employee.tenant_id
    effective_date = payload.pop('change_effective_date', None)
    change_reason = payload.pop('change_reason', None)

    if 'user_id' in payload:
        _assert_tenant_fk(User, payload.get('user_id'), tenant_id, 'user_id')
    if 'department_id' in payload:
        _assert_tenant_fk(Department, payload.get('department_id'), tenant_id, 'department_id')
    if 'manager_id' in payload:
        _assert_valid_manager(employee, payload.get('manager_id'), tenant_id)

    old_job = (employee.job_title, employee.department_id, employee.manager_id)
    old_department_id = employee.department_id
    old_status = employee.employment_status

    for key, value in payload.items():
        if key != 'tenant_id':
            setattr(employee, key, value)

    new_job = (employee.job_title, employee.department_id, employee.manager_id)
    if new_job != old_job:
        _clear_department_head_if_departing(employee, old_department_id, employee.department_id)
        _record_job_change(employee, effective_date, change_reason)

    if old_status != 'terminated' and employee.employment_status == 'terminated':
        Department.query.filter(
            Department.tenant_id == tenant_id,
            Department.head_employee_id == employee.id,
            Department.deleted_at.is_(None),
        ).update({'head_employee_id': None}, synchronize_session=False)

    log_event(
        'employee.update',
        'Employee',
        employee.id,
        tenant_id=tenant_id,
        metadata={
            'job_assignment_changed': new_job != old_job,
            'reason': change_reason,
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
