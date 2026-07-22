from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import LeaveBalance, LeaveRequest, LeaveType
from app.schemas.leave_schema import LeaveDecisionSchema, LeaveRequestCreateSchema, LeaveTypeCreateSchema
from app.services.leave_service import create_leave_request, decide_leave_request
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

leave_bp = Blueprint('leave', __name__, url_prefix='/leave')


@leave_bp.get('/types')
@jwt_required()
@permission_required('leave:create')
def list_leave_types():
    query = tenant_query(LeaveType).filter_by(is_active=True).order_by(LeaveType.name.asc())
    return success({'items': [item.to_dict() for item in query.all()]})


@leave_bp.post('/types')
@jwt_required()
@permission_required('leave:approve')
def create_leave_type():
    try:
        payload = LeaveTypeCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    leave_type = LeaveType(tenant_id=current_user.tenant_id, **payload)
    db.session.add(leave_type)
    db.session.commit()
    return success(leave_type.to_dict(), 'Leave type created', 201)


@leave_bp.post('/requests')
@jwt_required()
@permission_required('leave:create')
def submit_leave_request():
    try:
        payload = LeaveRequestCreateSchema().load(request.get_json() or {})
        request_obj = create_leave_request(payload, current_user.tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        return fail('LEAVE_REQUEST_FAILED', str(exc), 400)
    return success(request_obj.to_dict(), 'Leave request submitted', 201)


@leave_bp.get('/requests')
@jwt_required()
@permission_required('leave:create')
def list_leave_requests():
    page, per_page = get_pagination()
    query = tenant_query(LeaveRequest)
    if request.args.get('status'):
        query = query.filter(LeaveRequest.status == request.args['status'])
    if request.args.get('employee_id'):
        query = query.filter(LeaveRequest.employee_id == request.args['employee_id'])
    if current_user.has_role('EMPLOYEE') and current_user.employee_profile:
        query = query.filter(LeaveRequest.employee_id == current_user.employee_profile.id)
    return success(paginated_response(query.order_by(LeaveRequest.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)))


@leave_bp.patch('/requests/<request_id>/approve')
@jwt_required()
@permission_required('leave:approve')
def approve_leave(request_id):
    leave_request = tenant_query(LeaveRequest).filter_by(id=request_id).first_or_404()
    try:
        payload = LeaveDecisionSchema().load(request.get_json() or {})
        leave_request = decide_leave_request(leave_request, 'approved', current_user.id, payload.get('decision_notes'))
    except (ValidationError, ValueError) as err:
        return fail('LEAVE_APPROVAL_FAILED', getattr(err, 'messages', str(err)), 400)
    return success(leave_request.to_dict(), 'Leave request approved')


@leave_bp.patch('/requests/<request_id>/reject')
@jwt_required()
@permission_required('leave:approve')
def reject_leave(request_id):
    leave_request = tenant_query(LeaveRequest).filter_by(id=request_id).first_or_404()
    try:
        payload = LeaveDecisionSchema().load(request.get_json() or {})
        leave_request = decide_leave_request(leave_request, 'rejected', current_user.id, payload.get('decision_notes'))
    except (ValidationError, ValueError) as err:
        return fail('LEAVE_REJECTION_FAILED', getattr(err, 'messages', str(err)), 400)
    return success(leave_request.to_dict(), 'Leave request rejected')


@leave_bp.get('/balances')
@jwt_required()
@permission_required('leave:create')
def leave_balances():
    query = tenant_query(LeaveBalance)
    if request.args.get('employee_id'):
        query = query.filter(LeaveBalance.employee_id == request.args['employee_id'])
    if current_user.has_role('EMPLOYEE') and current_user.employee_profile:
        query = query.filter(LeaveBalance.employee_id == current_user.employee_profile.id)
    return success({'items': [balance.to_dict() for balance in query.all()]})
