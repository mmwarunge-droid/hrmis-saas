from datetime import date

from app.extensions import db
from app.models import Department, Employee
from app.services.audit_service import log_event
from app.services.employee_service import transfer_employees_department


def _active_department(tenant_id, department_id, field_name='department_id'):
    if not department_id:
        return None
    department = Department.query.filter_by(
        id=department_id,
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()
    if not department:
        raise ValueError(f'{field_name} is invalid for this tenant')
    return department


def _active_employee(tenant_id, employee_id, field_name='head_employee_id'):
    if not employee_id:
        return None
    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()
    if not employee or employee.employment_status == 'terminated':
        raise ValueError(f'{field_name} is invalid for this tenant')
    return employee


def _validate_parent(department, parent_id, tenant_id):
    if not parent_id:
        return None

    parent = _active_department(tenant_id, parent_id, 'parent_department_id')
    if department is not None and str(parent.id) == str(department.id):
        raise ValueError('A department cannot be its own parent')

    visited = set()
    current = parent
    while current is not None:
        current_id = str(current.id)
        if current_id in visited:
            raise ValueError('The department hierarchy already contains a cycle')
        visited.add(current_id)
        if department is not None and current_id == str(department.id):
            raise ValueError('Parent assignment would create a department cycle')
        if not current.parent_department_id:
            break
        current = Department.query.filter_by(
            id=current.parent_department_id,
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()
    return parent


def create_department(payload, tenant_id):
    payload = dict(payload)
    payload.pop('tenant_id', None)
    parent_id = payload.pop('parent_department_id', None)
    head_employee_id = payload.pop('head_employee_id', None)

    _validate_parent(None, parent_id, tenant_id)
    head = _active_employee(tenant_id, head_employee_id)

    department = Department(
        tenant_id=tenant_id,
        parent_department_id=parent_id,
        head_employee_id=head_employee_id,
        **payload,
    )
    db.session.add(department)
    db.session.flush()

    if head and str(head.department_id) != str(department.id):
        transfer_employees_department(
            [head],
            department.id,
            date.today(),
            'Assigned as department head',
            tenant_id,
            commit=False,
        )

    log_event(
        'department.create',
        'Department',
        department.id,
        tenant_id=tenant_id,
        metadata={'name': department.name},
    )
    db.session.commit()
    return department


def update_department(department, payload):
    payload = dict(payload)
    payload.pop('tenant_id', None)
    tenant_id = department.tenant_id

    if 'parent_department_id' in payload:
        _validate_parent(department, payload.get('parent_department_id'), tenant_id)
    if 'head_employee_id' in payload:
        head = _active_employee(tenant_id, payload.get('head_employee_id'))
    else:
        head = None

    for field in ('name', 'code', 'parent_department_id', 'head_employee_id'):
        if field in payload:
            setattr(department, field, payload[field])

    if 'head_employee_id' in payload and head and str(head.department_id) != str(department.id):
        transfer_employees_department(
            [head],
            department.id,
            date.today(),
            'Assigned as department head',
            tenant_id,
            commit=False,
        )

    log_event(
        'department.update',
        'Department',
        department.id,
        tenant_id=tenant_id,
        metadata={'name': department.name},
    )
    db.session.commit()
    return department


def archive_department(
    department,
    replacement_department_id,
    replacement_supplied,
    effective_date,
    reason,
):
    if department.deleted_at is not None:
        raise ValueError('Department is already archived')

    tenant_id = department.tenant_id
    if replacement_department_id and str(replacement_department_id) == str(department.id):
        raise ValueError('Replacement department must be different')

    replacement = _active_department(
        tenant_id,
        replacement_department_id,
        'replacement_department_id',
    )
    employees = Employee.query.filter(
        Employee.tenant_id == tenant_id,
        Employee.department_id == department.id,
        Employee.deleted_at.is_(None),
    ).all()

    if employees and not replacement_supplied:
        raise ValueError('Choose a replacement department or explicitly unassign employees')

    changed = transfer_employees_department(
        employees,
        replacement.id if replacement else None,
        effective_date,
        reason,
        tenant_id,
        commit=False,
    )

    Department.query.filter(
        Department.tenant_id == tenant_id,
        Department.parent_department_id == department.id,
        Department.deleted_at.is_(None),
    ).update({'parent_department_id': None}, synchronize_session=False)

    department.head_employee_id = None
    department.soft_delete()
    log_event(
        'department.archive',
        'Department',
        department.id,
        tenant_id=tenant_id,
        metadata={
            'replacement_department_id': str(replacement.id) if replacement else None,
            'employees_reassigned': len(changed),
            'reason': reason,
        },
    )
    db.session.commit()
    return department, changed


def restore_department(department):
    if department.deleted_at is None:
        raise ValueError('Department is already active')

    department.deleted_at = None
    log_event(
        'department.restore',
        'Department',
        department.id,
        tenant_id=department.tenant_id,
        metadata={'name': department.name},
    )
    db.session.commit()
    return department
