from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import Goal
from app.schemas.goal_schema import (
    GoalCheckInSchema,
    GoalCreateSchema,
    GoalUpdateSchema,
)
from app.services.goal_service import (
    add_check_in,
    create_goal,
    goal_scope_query,
    goal_summary,
    update_goal,
)
from app.utils.decorators import permission_required, request_tenant_id, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success


goal_bp = Blueprint('goals', __name__, url_prefix='/goals')


def _apply_filters(query):
    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(or_(
            db.func.lower(Goal.title).like(like),
            db.func.lower(Goal.description).like(like),
            db.func.lower(Goal.unit).like(like),
        ))
    for field in ('status', 'health', 'owner_type'):
        value = request.args.get(field, '').strip()
        if value:
            query = query.filter(getattr(Goal, field) == value)
    employee_id = request.args.get('employee_id')
    if employee_id:
        query = query.filter(Goal.employee_id == employee_id)
    department_id = request.args.get('department_id')
    if department_id:
        query = query.filter(Goal.department_id == department_id)
    return query


def _apply_sort(query):
    sort = request.args.get('sort', 'due_date').strip()
    direction = request.args.get('direction', 'asc').strip()
    column = {
        'title': Goal.title,
        'due_date': Goal.due_date,
        'progress': Goal.progress_percent,
        'health': Goal.health,
        'created_at': Goal.created_at,
    }.get(sort, Goal.due_date)
    order = column.desc() if direction == 'desc' else column.asc()
    return query.order_by(order, Goal.id.asc())


@goal_bp.get('')
@jwt_required()
@permission_required('goal:read')
def list_goals():
    page, per_page = get_pagination(default_per_page=15)
    query = goal_scope_query(current_user, tenant_query(Goal))
    query = _apply_sort(_apply_filters(query))
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    data = paginated_response(pagination)
    data['items'] = [item.to_dict() for item in pagination.items]
    return success(data)


@goal_bp.get('/summary')
@jwt_required()
@permission_required('goal:read')
def get_goal_summary():
    return success(goal_summary(current_user))


@goal_bp.post('')
@jwt_required()
@permission_required('goal:manage')
def post_goal():
    try:
        payload = GoalCreateSchema().load(request.get_json() or {})
        tenant_id = request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required for goals', 422)
        goal = create_goal(payload, tenant_id, current_user)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        db.session.rollback()
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('GOAL_CREATE_FAILED', str(exc), 400)
    return success(goal.to_dict(include_check_ins=True), 'Goal created', 201)


@goal_bp.get('/<goal_id>')
@jwt_required()
@permission_required('goal:read')
def get_goal(goal_id):
    goal = goal_scope_query(current_user, tenant_query(Goal)).filter_by(
        id=goal_id,
    ).first_or_404()
    return success(goal.to_dict(include_check_ins=True))


@goal_bp.patch('/<goal_id>')
@jwt_required()
@permission_required('goal:manage')
def patch_goal(goal_id):
    goal = goal_scope_query(current_user, tenant_query(Goal)).filter_by(
        id=goal_id,
    ).first_or_404()
    try:
        payload = GoalUpdateSchema().load(request.get_json() or {})
        goal = update_goal(goal, payload, current_user)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        db.session.rollback()
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('GOAL_UPDATE_FAILED', str(exc), 400)
    return success(goal.to_dict(include_check_ins=True), 'Goal updated')


@goal_bp.post('/<goal_id>/check-ins')
@jwt_required()
@permission_required('goal:checkin')
def post_check_in(goal_id):
    goal = goal_scope_query(current_user, tenant_query(Goal)).filter_by(
        id=goal_id,
    ).first_or_404()
    try:
        payload = GoalCheckInSchema().load(request.get_json() or {})
        check_in = add_check_in(goal, payload, current_user)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        db.session.rollback()
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('GOAL_CHECK_IN_FAILED', str(exc), 400)
    return success({
        'goal': goal.to_dict(include_check_ins=True),
        'check_in': check_in.to_dict(),
    }, 'Goal progress updated', 201)
