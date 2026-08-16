from datetime import timedelta

from app.extensions import db
from app.models import (
    Employee,
    EmployeeOnboardingTask,
    OnboardingTask,
    OnboardingTemplate,
    Tenant,
    Role,
    User,
    UserRole,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.notification_service import create_notification


def _assignable_user(employee, role_name):
    if role_name == 'EMPLOYEE':
        return employee.user
    if role_name == 'MANAGER':
        return employee.manager.user if employee.manager else None
    return User.query.filter(
        User.tenant_id == employee.tenant_id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
        User.role_links.any(
            UserRole.role.has(Role.name == role_name),
        ),
    ).order_by(User.first_name.asc(), User.last_name.asc()).first()


def create_template(payload, tenant_id):
    tasks = payload.pop('tasks', [])
    template = OnboardingTemplate(tenant_id=tenant_id, **payload)
    db.session.add(template)
    db.session.flush()
    for task in tasks:
        db.session.add(
            OnboardingTask(
                tenant_id=tenant_id,
                template_id=template.id,
                **task,
            )
        )
    log_event(
        'onboarding.template_create',
        'OnboardingTemplate',
        template.id,
        tenant_id=tenant_id,
    )
    db.session.commit()
    return template


def update_template(template, payload):
    tasks = payload.pop('tasks', None)
    for field in ('name', 'description', 'is_active'):
        if field in payload:
            setattr(template, field, payload[field])
    if tasks is not None:
        if template.tasks and any(task.assignments for task in template.tasks):
            raise ValueError(
                'Templates with assigned tasks cannot replace their task list. '
                'Archive the template and create a new version instead.'
            )
        template.tasks.clear()
        db.session.flush()
        for task in tasks:
            template.tasks.append(
                OnboardingTask(
                    tenant_id=template.tenant_id,
                    **task,
                )
            )
    log_event(
        'onboarding.template_update',
        'OnboardingTemplate',
        template.id,
        tenant_id=template.tenant_id,
    )
    db.session.commit()
    return template


def assign_template(employee_id, template_id, tenant_id):
    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()
    template = OnboardingTemplate.query.filter_by(
        id=template_id,
        tenant_id=tenant_id,
        is_active=True,
    ).first()
    if not employee or not template:
        raise ValueError('Invalid employee_id or template_id for this tenant')

    tenant = db.session.get(Tenant, tenant_id)
    organization_name = (
        tenant.name
        if tenant and tenant.name
        else 'Your organization'
    )

    created = []
    for task in template.tasks:
        existing = EmployeeOnboardingTask.query.filter_by(
            tenant_id=tenant_id,
            employee_id=employee.id,
            task_id=task.id,
        ).first()
        if existing:
            created.append(existing)
            continue
        assignee = _assignable_user(employee, task.assignee_role)
        due_date = employee.hire_date + timedelta(
            days=task.due_days_after_start or 0,
        )
        status = 'overdue' if due_date < utcnow().date() else 'pending'
        assignment = EmployeeOnboardingTask(
            tenant_id=tenant_id,
            employee_id=employee.id,
            task_id=task.id,
            assigned_to_user_id=assignee.id if assignee else None,
            due_date=due_date,
            status=status,
        )
        db.session.add(assignment)
        db.session.flush()
        created.append(assignment)
        if assignee:
            create_notification(
                tenant_id=tenant_id,
                user_id=assignee.id,
                title=(
                    f'{organization_name} assigned you a Kinetic task'
                ),
                body=(
                    f'{task.title} · due {due_date.isoformat()}'
                ),
                notification_type='onboarding',
                action_url='/tasks',
                priority='high' if status == 'overdue' else 'normal',
                metadata={
                    'assignment_id': str(assignment.id),
                    'employee_id': str(employee.id),
                    'task_id': str(task.id),
                    'template_id': str(template.id),
                },
            )
    log_event(
        'onboarding.assign',
        'Employee',
        employee.id,
        tenant_id=tenant_id,
        metadata={'template_id': str(template.id)},
    )
    db.session.commit()
    return created


def update_assignment(assignment, payload, actor):
    if 'assigned_to_user_id' in payload:
        assignee_id = payload['assigned_to_user_id']
        if assignee_id:
            assignee = User.query.filter_by(
                id=assignee_id,
                tenant_id=assignment.tenant_id,
                is_active=True,
                deleted_at=None,
            ).first()
            if not assignee:
                raise ValueError('Assignee is invalid for this organization')
        assignment.assigned_to_user_id = assignee_id

    if 'status' in payload:
        assignment.status = payload['status']
        if assignment.status == 'completed':
            assignment.completed_at = utcnow()
        elif assignment.status not in {'completed', 'waived'}:
            assignment.completed_at = None
    if 'completion_notes' in payload:
        assignment.completion_notes = payload['completion_notes']

    log_event(
        'onboarding.assignment_update',
        'EmployeeOnboardingTask',
        assignment.id,
        tenant_id=assignment.tenant_id,
        metadata={'status': assignment.status},
    )
    db.session.commit()
    return assignment


def complete_assignment(assignment, notes=None):
    assignment.status = 'completed'
    assignment.completed_at = utcnow()
    assignment.completion_notes = notes
    log_event(
        'onboarding.task_complete',
        'EmployeeOnboardingTask',
        assignment.id,
        tenant_id=assignment.tenant_id,
    )
    db.session.commit()
    return assignment
