from datetime import timedelta

from app.extensions import db
from app.models import Employee, EmployeeOnboardingTask, OnboardingTask, OnboardingTemplate
from app.models.base import utcnow
from app.services.audit_service import log_event


def create_template(payload, tenant_id):
    tasks = payload.pop('tasks', [])
    template = OnboardingTemplate(tenant_id=tenant_id, **payload)
    db.session.add(template)
    db.session.flush()
    for task in tasks:
        db.session.add(OnboardingTask(tenant_id=tenant_id, template_id=template.id, **task))
    log_event('onboarding.template_create', 'OnboardingTemplate', template.id, tenant_id=tenant_id)
    db.session.commit()
    return template


def assign_template(employee_id, template_id, tenant_id):
    employee = Employee.query.filter_by(id=employee_id, tenant_id=tenant_id, deleted_at=None).first()
    template = OnboardingTemplate.query.filter_by(id=template_id, tenant_id=tenant_id, is_active=True).first()
    if not employee or not template:
        raise ValueError('Invalid employee_id or template_id for this tenant')
    created = []
    for task in template.tasks:
        due_date = employee.hire_date + timedelta(days=task.due_days_after_start or 0)
        assignment = EmployeeOnboardingTask(tenant_id=tenant_id, employee_id=employee.id, task_id=task.id, due_date=due_date)
        db.session.add(assignment)
        created.append(assignment)
    log_event('onboarding.assign', 'Employee', employee.id, tenant_id=tenant_id, metadata={'template_id': str(template.id)})
    db.session.commit()
    return created


def complete_assignment(assignment, notes=None):
    assignment.status = 'completed'
    assignment.completed_at = utcnow()
    assignment.completion_notes = notes
    log_event('onboarding.task_complete', 'EmployeeOnboardingTask', assignment.id, tenant_id=assignment.tenant_id)
    db.session.commit()
    return assignment
