from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app.models import EmployeeOnboardingTask, OnboardingTemplate
from app.schemas.onboarding_schema import OnboardingAssignSchema, OnboardingTaskCompleteSchema, OnboardingTemplateCreateSchema
from app.services.onboarding_service import assign_template, complete_assignment, create_template
from app.utils.decorators import permission_required, tenant_query
from app.utils.response import fail, success

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


@onboarding_bp.get('/templates')
@jwt_required()
@permission_required('onboarding:create')
def list_templates():
    query = tenant_query(OnboardingTemplate).filter_by(is_active=True).order_by(OnboardingTemplate.name.asc())
    return success({'items': [template.to_dict() for template in query.all()]})


@onboarding_bp.post('/templates')
@jwt_required()
@permission_required('onboarding:create')
def create_onboarding_template():
    try:
        payload = OnboardingTemplateCreateSchema().load(request.get_json() or {})
        template = create_template(payload, current_user.tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    return success(template.to_dict(), 'Onboarding template created', 201)


@onboarding_bp.post('/assign')
@jwt_required()
@permission_required('onboarding:assign')
def assign_onboarding():
    try:
        payload = OnboardingAssignSchema().load(request.get_json() or {})
        assignments = assign_template(payload['employee_id'], payload['template_id'], current_user.tenant_id)
    except (ValidationError, ValueError) as err:
        return fail('ONBOARDING_ASSIGN_FAILED', getattr(err, 'messages', str(err)), 400)
    return success({'items': [assignment.to_dict() for assignment in assignments]}, 'Onboarding assigned', 201)


@onboarding_bp.get('/my-tasks')
@jwt_required()
def my_tasks():
    query = tenant_query(EmployeeOnboardingTask)
    if current_user.employee_profile:
        query = query.filter(EmployeeOnboardingTask.employee_id == current_user.employee_profile.id)
    elif not current_user.has_any_role({'HR_CONSULTANT', 'CLIENT_ADMIN', 'SUPER_ADMIN'}):
        return fail('EMPLOYEE_PROFILE_REQUIRED', 'No employee profile is linked to this user', 400)
    return success({'items': [task.to_dict() for task in query.order_by(EmployeeOnboardingTask.due_date.asc()).all()]})


@onboarding_bp.patch('/tasks/<assignment_id>/complete')
@jwt_required()
def complete_task(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(id=assignment_id).first_or_404()
    if current_user.has_role('EMPLOYEE') and current_user.employee_profile and assignment.employee_id != current_user.employee_profile.id:
        return fail('FORBIDDEN', 'You cannot complete another employee\'s task', 403)
    try:
        payload = OnboardingTaskCompleteSchema().load(request.get_json() or {})
        assignment = complete_assignment(assignment, payload.get('completion_notes'))
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    return success(assignment.to_dict(), 'Task completed')
