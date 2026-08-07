from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Employee,
    EmployeeOnboardingTask,
    OnboardingTask,
    OnboardingTemplate,
)
from app.schemas.onboarding_schema import (
    OnboardingAssignSchema,
    OnboardingAssignmentUpdateSchema,
    OnboardingTaskCompleteSchema,
    OnboardingTemplateCreateSchema,
    OnboardingTemplateUpdateSchema,
)
from app.services.onboarding_service import (
    assign_template,
    complete_assignment,
    create_template,
    update_assignment,
    update_template,
)
from app.utils.decorators import (
    permission_required,
    request_tenant_id,
    tenant_query,
)
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


def _serialize_assignment(assignment):
    data = assignment.to_dict()
    data.update({
        'employee_name': assignment.employee.full_name,
        'employee_number': assignment.employee.employee_number,
        'task_title': assignment.task.title,
        'task_description': assignment.task.description,
        'template_id': str(assignment.task.template_id),
        'template_name': assignment.task.template.name,
        'assignee_role': assignment.task.assignee_role,
        'assigned_to_name': (
            assignment.assigned_to.full_name
            if assignment.assigned_to
            else None
        ),
    })
    return data


@onboarding_bp.get('/templates')
@jwt_required()
@permission_required('onboarding:create')
def list_templates():
    query = tenant_query(OnboardingTemplate).order_by(
        OnboardingTemplate.is_active.desc(),
        OnboardingTemplate.name.asc(),
    )
    if request.args.get('active', '').lower() == 'true':
        query = query.filter(OnboardingTemplate.is_active.is_(True))
    return success({'items': [template.to_dict() for template in query.all()]})


@onboarding_bp.post('/templates')
@jwt_required()
@permission_required('onboarding:create')
def create_onboarding_template():
    try:
        payload = OnboardingTemplateCreateSchema().load(
            request.get_json() or {},
        )
        tenant_id = request_tenant_id(payload)
        if not tenant_id:
            return fail(
                'TENANT_REQUIRED',
                'tenant_id is required for onboarding templates',
                422,
            )
        template = create_template(payload, tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_TEMPLATE_FAILED', str(exc), 400)
    return success(template.to_dict(), 'Onboarding template created', 201)


@onboarding_bp.patch('/templates/<template_id>')
@jwt_required()
@permission_required('onboarding:create')
def patch_onboarding_template(template_id):
    template = tenant_query(OnboardingTemplate).filter_by(
        id=template_id,
    ).first_or_404()
    try:
        payload = OnboardingTemplateUpdateSchema().load(
            request.get_json() or {},
        )
        template = update_template(template, payload)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_TEMPLATE_FAILED', str(exc), 400)
    return success(template.to_dict(), 'Onboarding template updated')


@onboarding_bp.post('/assign')
@jwt_required()
@permission_required('onboarding:assign')
def assign_onboarding():
    try:
        payload = OnboardingAssignSchema().load(
            request.get_json() or {},
        )
        tenant_id = request_tenant_id(payload)
        if not tenant_id:
            return fail(
                'TENANT_REQUIRED',
                'tenant_id is required for onboarding assignments',
                422,
            )
        assignments = assign_template(
            payload['employee_id'],
            payload['template_id'],
            tenant_id,
        )
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail(
            'ONBOARDING_ASSIGN_FAILED',
            getattr(err, 'messages', str(err)),
            400,
        )
    return success(
        {'items': [_serialize_assignment(item) for item in assignments]},
        'Onboarding assigned',
        201,
    )


@onboarding_bp.get('/assignments')
@jwt_required()
@permission_required('onboarding:assign')
def list_assignments():
    page, per_page = get_pagination(default_per_page=15)
    query = tenant_query(EmployeeOnboardingTask).join(
        EmployeeOnboardingTask.employee,
    ).join(EmployeeOnboardingTask.task)
    status = request.args.get('status', '').strip()
    if status:
        query = query.filter(EmployeeOnboardingTask.status == status)
    employee_id = request.args.get('employee_id')
    if employee_id:
        query = query.filter(EmployeeOnboardingTask.employee_id == employee_id)
    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            db.func.lower(Employee.first_name).like(like),
            db.func.lower(Employee.last_name).like(like),
            db.func.lower(OnboardingTask.title).like(like),
        ))
    pagination = query.order_by(
        EmployeeOnboardingTask.due_date.asc(),
        EmployeeOnboardingTask.created_at.desc(),
    ).paginate(page=page, per_page=per_page, error_out=False)
    data = paginated_response(pagination)
    data['items'] = [_serialize_assignment(item) for item in pagination.items]
    return success(data)


@onboarding_bp.get('/summary')
@jwt_required()
@permission_required('onboarding:assign')
def onboarding_summary():
    query = tenant_query(EmployeeOnboardingTask)
    return success({
        'total': query.count(),
        'open': query.filter(
            EmployeeOnboardingTask.status.in_(
                ['pending', 'in_progress', 'overdue'],
            ),
        ).count(),
        'overdue': query.filter_by(status='overdue').count(),
        'completed': query.filter_by(status='completed').count(),
        'waived': query.filter_by(status='waived').count(),
    })


@onboarding_bp.patch('/assignments/<assignment_id>')
@jwt_required()
@permission_required('onboarding:assign')
def patch_assignment(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).first_or_404()
    try:
        payload = OnboardingAssignmentUpdateSchema().load(
            request.get_json() or {},
        )
        assignment = update_assignment(assignment, payload, current_user)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_ASSIGNMENT_FAILED', str(exc), 400)
    return success(
        _serialize_assignment(assignment),
        'Onboarding assignment updated',
    )


@onboarding_bp.get('/my-tasks')
@jwt_required()
def my_tasks():
    query = tenant_query(EmployeeOnboardingTask)
    if current_user.employee_profile:
        query = query.filter(or_(
            EmployeeOnboardingTask.employee_id
            == current_user.employee_profile.id,
            EmployeeOnboardingTask.assigned_to_user_id == current_user.id,
        ))
    elif not current_user.has_any_role(
        {'HR_CONSULTANT', 'CLIENT_ADMIN', 'SUPER_ADMIN'},
    ):
        return fail(
            'EMPLOYEE_PROFILE_REQUIRED',
            'No employee profile is linked to this user',
            400,
        )
    items = query.order_by(
        EmployeeOnboardingTask.due_date.asc(),
    ).all()
    return success({'items': [_serialize_assignment(item) for item in items]})


@onboarding_bp.patch('/tasks/<assignment_id>/complete')
@jwt_required()
def complete_task(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).first_or_404()
    owns_task = (
        current_user.employee_profile
        and assignment.employee_id == current_user.employee_profile.id
    )
    assigned_task = assignment.assigned_to_user_id == current_user.id
    if not owns_task and not assigned_task and not current_user.has_any_role(
        {'HR_CONSULTANT', 'CLIENT_ADMIN', 'SUPER_ADMIN'},
    ):
        return fail(
            'FORBIDDEN',
            'You cannot complete this onboarding task',
            403,
        )
    try:
        payload = OnboardingTaskCompleteSchema().load(
            request.get_json() or {},
        )
        assignment = complete_assignment(
            assignment,
            payload.get('completion_notes'),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    return success(
        _serialize_assignment(assignment),
        'Task completed',
    )
