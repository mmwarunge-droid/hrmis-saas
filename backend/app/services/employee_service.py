from app.extensions import db
from app.models import Department, Employee, JobHistory
from app.services.audit_service import log_event


def _assert_tenant_fk(model, object_id, tenant_id, field_name):
    if not object_id:
        return
    obj = model.query.filter_by(id=object_id, tenant_id=tenant_id).first()
    if not obj:
        raise ValueError(f'{field_name} is invalid for this tenant')


def create_employee(payload, tenant_id):
    _assert_tenant_fk(Department, payload.get('department_id'), tenant_id, 'department_id')
    _assert_tenant_fk(Employee, payload.get('manager_id'), tenant_id, 'manager_id')
    employee = Employee(tenant_id=tenant_id, **payload)
    db.session.add(employee)
    db.session.flush()
    if employee.job_title:
        db.session.add(JobHistory(
            tenant_id=tenant_id,
            employee_id=employee.id,
            job_title=employee.job_title,
            department_id=employee.department_id,
            manager_id=employee.manager_id,
            start_date=employee.hire_date,
            reason='Initial hire',
        ))
    log_event('employee.create', 'Employee', employee.id, tenant_id=tenant_id)
    db.session.commit()
    return employee


def update_employee(employee, payload):
    tenant_id = employee.tenant_id
    _assert_tenant_fk(Department, payload.get('department_id'), tenant_id, 'department_id')
    _assert_tenant_fk(Employee, payload.get('manager_id'), tenant_id, 'manager_id')
    old_job = (employee.job_title, employee.department_id, employee.manager_id)
    for key, value in payload.items():
        if key != 'tenant_id':
            setattr(employee, key, value)
    new_job = (employee.job_title, employee.department_id, employee.manager_id)
    if new_job != old_job and employee.job_title:
        db.session.add(JobHistory(
            tenant_id=tenant_id,
            employee_id=employee.id,
            job_title=employee.job_title,
            department_id=employee.department_id,
            manager_id=employee.manager_id,
            start_date=employee.hire_date,
            reason='Profile update',
        ))
    log_event('employee.update', 'Employee', employee.id, tenant_id=tenant_id)
    db.session.commit()
    return employee


def soft_delete_employee(employee):
    employee.soft_delete()
    log_event('employee.delete', 'Employee', employee.id, tenant_id=employee.tenant_id)
    db.session.commit()
