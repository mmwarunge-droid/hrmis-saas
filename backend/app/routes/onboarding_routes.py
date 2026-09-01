from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Employee,
    EmployeeOnboardingTask,
    OnboardingResource,
    OnboardingTask,
    OnboardingTemplate,
    OnboardingTrainingAttempt,
)
from app.schemas.onboarding_schema import (
    OnboardingAssignSchema,
    OnboardingAssignmentUpdateSchema,
    OnboardingRetakeSchema,
    OnboardingTaskCompleteSchema,
    OnboardingVideoProgressSchema,
    OnboardingTemplateCreateSchema,
    OnboardingTemplateUpdateSchema,
)
from app.services.onboarding_service import (
    assign_template,
    can_access_resource,
    complete_assignment,
    create_resource,
    create_template,
    mark_assignment_viewed,
    record_video_progress,
    retake_assignment,
    update_assignment,
    update_template,
    video_progress_state,
)
from app.utils.decorators import (
    permission_required,
    request_tenant_id,
    tenant_query,
)
from app.utils.file_storage import send_stored_file
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')

UNRESTRICTED_ONBOARDING_ROLES = {
    'HR_CONSULTANT',
    'CLIENT_ADMIN',
    'SUPER_ADMIN',
}


def _onboarding_admin_scope():
    if current_user.has_any_role(UNRESTRICTED_ONBOARDING_ROLES):
        return 'tenant'
    if current_user.has_role('MANAGER') and current_user.employee_profile:
        return 'team'
    return None


def _forbidden_onboarding_admin():
    return fail(
        'FORBIDDEN',
        'You cannot administer onboarding for this employee',
        403,
    )


def _manager_can_administer(employee):
    profile = current_user.employee_profile
    return bool(
        current_user.has_role('MANAGER')
        and profile
        and str(employee.manager_id) == str(profile.id)
    )


def _is_assigned_task_actor(assignment):
    owns_task = (
        current_user.employee_profile
        and assignment.employee_id == current_user.employee_profile.id
    )
    assigned_task = assignment.assigned_to_user_id == current_user.id
    return bool(owns_task or assigned_task)


def _can_act_on_assignment(assignment):
    owns_task = (
        current_user.employee_profile
        and assignment.employee_id == current_user.employee_profile.id
    )
    assigned_task = assignment.assigned_to_user_id == current_user.id
    return bool(
        owns_task
        or assigned_task
        or current_user.has_any_role(
            {'HR_CONSULTANT', 'CLIENT_ADMIN', 'SUPER_ADMIN'},
        )
    )


def _serialize_assignment(assignment):
    data = assignment.to_dict()
    data.update({
        'tenant_id': str(assignment.tenant_id),
        'employee_name': assignment.employee.full_name,
        'employee_number': assignment.employee.employee_number,
        'task_title': assignment.task.title,
        'task_description': assignment.task.description,
        'task_type': assignment.task.task_type,
        'requires_acknowledgement': (
            assignment.task.requires_acknowledgement
        ),
        'resource': (
            assignment.task.resource.to_dict()
            if assignment.task.resource
            else None
        ),
        'template_id': str(assignment.task.template_id),
        'template_name': assignment.task.template.name,
        'assignee_role': assignment.task.assignee_role,
        'video_progress': video_progress_state(assignment),
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


@onboarding_bp.post('/resources')
@jwt_required()
@permission_required('onboarding:create')
def upload_onboarding_resource():
    try:
        tenant_id = request_tenant_id()
        if not tenant_id:
            return fail(
                'TENANT_REQUIRED',
                'Select an organization before uploading training material',
                422,
            )
        resource = create_resource(
            request.files.get('file'),
            tenant_id,
            current_user.id,
            duration_seconds=request.form.get('duration_seconds'),
        )
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_RESOURCE_FAILED', str(exc), 400)
    return success(resource.to_dict(), 'Training resource uploaded', 201)


@onboarding_bp.get('/resources/<resource_id>/content')
@jwt_required()
def onboarding_resource_content(resource_id):
    resource = tenant_query(OnboardingResource).filter_by(
        id=resource_id,
    ).first_or_404()
    if not can_access_resource(resource):
        return fail('FORBIDDEN', 'You cannot access this training resource', 403)

    response = send_stored_file(
        resource.file_path,
        resource.original_filename,
        as_attachment=False,
        mimetype=resource.mime_type,
    )
    response.headers['Content-Security-Policy'] = (
        "default-src 'none'; frame-ancestors 'self'"
    )
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


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
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

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
        employee = Employee.query.filter_by(
            id=payload['employee_id'],
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()
        if scope == 'team' and (
            not employee or not _manager_can_administer(employee)
        ):
            return _forbidden_onboarding_admin()
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
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

    page, per_page = get_pagination(default_per_page=15)
    query = tenant_query(EmployeeOnboardingTask).join(
        EmployeeOnboardingTask.employee,
    ).join(EmployeeOnboardingTask.task)
    if scope == 'team':
        query = query.filter(
            Employee.manager_id == current_user.employee_profile.id,
        )
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
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

    query = tenant_query(EmployeeOnboardingTask)
    if scope == 'team':
        query = query.join(
            EmployeeOnboardingTask.employee,
        ).filter(
            Employee.manager_id == current_user.employee_profile.id,
        )
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
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).first_or_404()
    if scope == 'team' and not _manager_can_administer(
        assignment.employee,
    ):
        return _forbidden_onboarding_admin()
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


@onboarding_bp.get('/assignments/<assignment_id>/attempts')
@jwt_required()
@permission_required('onboarding:assign')
def assignment_attempts(assignment_id):
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).first_or_404()
    if scope == 'team' and not _manager_can_administer(assignment.employee):
        return _forbidden_onboarding_admin()

    attempts = OnboardingTrainingAttempt.query.filter_by(
        tenant_id=assignment.tenant_id,
        assignment_id=assignment.id,
    ).order_by(OnboardingTrainingAttempt.attempt_number.desc()).all()

    return success({
        'assignment': _serialize_assignment(assignment),
        'items': [attempt.to_dict() for attempt in attempts],
    })


@onboarding_bp.post('/assignments/<assignment_id>/retake')
@jwt_required()
@permission_required('onboarding:assign')
def retake_onboarding_assignment(assignment_id):
    scope = _onboarding_admin_scope()
    if not scope:
        return _forbidden_onboarding_admin()

    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).with_for_update().first_or_404()
    if scope == 'team' and not _manager_can_administer(assignment.employee):
        return _forbidden_onboarding_admin()

    try:
        payload = OnboardingRetakeSchema().load(request.get_json() or {})
        assignment = retake_assignment(
            assignment,
            current_user,
            reason=payload['reason'],
            due_date=payload.get('due_date'),
            grant_additional_attempts=payload.get(
                'grant_additional_attempts',
                0,
            ),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_RETAKE_FAILED', str(exc), 400)

    return success(
        _serialize_assignment(assignment),
        'Training retake assigned',
        201,
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


@onboarding_bp.patch('/tasks/<assignment_id>/view')
@jwt_required()
def view_task_resource(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).first_or_404()
    if not _can_act_on_assignment(assignment):
        return fail(
            'FORBIDDEN',
            'You cannot view this onboarding task',
            403,
        )
    if not assignment.task.resource_id:
        return fail(
            'ONBOARDING_RESOURCE_NOT_FOUND',
            'This onboarding task has no training resource',
            400,
        )
    assignment = mark_assignment_viewed(assignment)
    return success(_serialize_assignment(assignment), 'Training resource viewed')


@onboarding_bp.patch('/tasks/<assignment_id>/video-progress')
@jwt_required()
def update_video_progress(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).with_for_update().first_or_404()
    if not _is_assigned_task_actor(assignment):
        return fail(
            'FORBIDDEN',
            'Only the assigned user can record video training progress',
            403,
        )
    try:
        payload = OnboardingVideoProgressSchema().load(
            request.get_json() or {},
        )
        assignment, progress = record_video_progress(
            assignment,
            event=payload['event'],
            position_seconds=payload['position_seconds'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_VIDEO_PROGRESS_FAILED', str(exc), 400)

    data = _serialize_assignment(assignment)
    data['video_progress'] = progress
    return success(data, 'Video progress recorded')


@onboarding_bp.patch('/tasks/<assignment_id>/complete')
@jwt_required()
def complete_task(assignment_id):
    assignment = tenant_query(EmployeeOnboardingTask).filter_by(
        id=assignment_id,
    ).with_for_update().first_or_404()
    if (
        assignment.task.task_type == 'video'
        and not _is_assigned_task_actor(assignment)
    ):
        return fail(
            'FORBIDDEN',
            'Only the assigned user can complete video training',
            403,
        )
    if not _can_act_on_assignment(assignment):
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
            acknowledged=payload.get('acknowledged', False),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('ONBOARDING_TASK_FAILED', str(exc), 400)
    return success(
        _serialize_assignment(assignment),
        'Task completed',
    )
