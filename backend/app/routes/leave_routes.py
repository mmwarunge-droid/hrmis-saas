from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import false

from app.extensions import db
from app.models import (
    LeaveBalance,
    LeaveLedgerEntry,
    LeaveRequest,
    LeaveType,
    Tenant,
)
from app.schemas.leave_schema import (
    LeaveAccrualRunSchema,
    LeaveBalanceAdjustmentSchema,
    LeaveBalanceInitializeSchema,
    LeaveCancellationSchema,
    LeaveDecisionSchema,
    LeaveGovernanceSchema,
    LeavePolicyPackApplySchema,
    LeaveRequestCreateSchema,
    LeaveTypeCreateSchema,
)
from app.services.leave_accrual_service import (
    adjust_leave_balance,
    balance_scope_query,
    ledger_scope_query,
    run_scheduled_accruals,
)
from app.services.leave_policy_service import (
    apply_standard_policy_pack,
    can_configure_leave,
    configure_leave_governance,
    initialize_leave_balances,
    leave_setup_status,
)
from app.services.leave_service import (
    cancel_leave_request,
    create_leave_request,
    decide_leave_request,
    request_scope_query,
)
from app.utils.decorators import (
    permission_required,
    request_tenant_id,
    tenant_query,
)
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

leave_bp = Blueprint('leave', __name__, url_prefix='/leave')


def _tenant_or_error(payload=None):
    tenant_id = request_tenant_id(payload)
    if not tenant_id:
        return None, fail(
            'TENANT_REQUIRED',
            'tenant_id is required for time-off operations',
            422,
        )
    tenant = db.session.get(Tenant, tenant_id)
    if not tenant or tenant.deleted_at is not None:
        return None, fail(
            'TENANT_NOT_FOUND',
            'Organization was not found',
            404,
        )
    return tenant, None


def _serialize_request(leave_request):
    data = leave_request.to_dict()
    owns_request = bool(
        current_user.employee_profile
        and str(current_user.employee_profile.id)
        == str(leave_request.employee_id)
    )
    data['can_decide'] = bool(
        leave_request.status == 'pending'
        and leave_request.required_approver_id
        and str(leave_request.required_approver_id)
        == str(current_user.id)
        and str(leave_request.requested_by_user_id)
        != str(current_user.id)
        and (
            not leave_request.employee.user_id
            or str(leave_request.employee.user_id)
            != str(current_user.id)
        )
    )
    data['can_cancel'] = bool(
        leave_request.status in {'pending', 'approved'}
        and (
            owns_request
            or can_configure_leave(current_user)
        )
        and (
            leave_request.status != 'approved'
            or leave_request.start_date > date.today()
        )
    )
    data['employee_name'] = leave_request.employee.full_name
    data['leave_type_name'] = leave_request.leave_type.name
    data['required_approver_name'] = (
        leave_request.required_approver.full_name
        if leave_request.required_approver
        else None
    )
    return data


def _serialize_ledger(entry):
    data = entry.to_dict()
    data['employee_name'] = entry.employee.full_name
    data['leave_type_name'] = entry.leave_type.name
    data['actor_name'] = (
        entry.actor.full_name
        if entry.actor
        else 'Scheduled allocation'
    )
    return data


@leave_bp.get('/setup')
@jwt_required()
@permission_required('leave:create')
def get_leave_setup():
    tenant, error = _tenant_or_error()
    if error:
        return error
    try:
        data = leave_setup_status(tenant.id, current_user)
    except ValueError as exc:
        return fail('LEAVE_SETUP_FAILED', str(exc), 400)
    return success(data)


@leave_bp.patch('/setup/governance')
@jwt_required()
@permission_required('leave:approve')
def patch_leave_governance():
    try:
        payload = LeaveGovernanceSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        if not can_configure_leave(current_user):
            return fail(
                'FORBIDDEN',
                'Only organization owners and HR administrators '
                'can configure leave governance',
                403,
            )
        configure_leave_governance(
            tenant.id,
            current_user,
            payload['organization_owner_user_id'],
            payload['alternate_approver_user_id'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_GOVERNANCE_FAILED', str(exc), 400)

    return success(
        leave_setup_status(tenant.id, current_user),
        'Leave governance updated',
    )


@leave_bp.post('/setup/standard-pack')
@jwt_required()
@permission_required('leave:approve')
def apply_leave_standard_pack():
    try:
        payload = LeavePolicyPackApplySchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        if not can_configure_leave(current_user):
            return fail(
                'FORBIDDEN',
                'Only organization owners and HR administrators '
                'can configure leave policies',
                403,
            )
        policies, balance_result = apply_standard_policy_pack(
            tenant.id,
            current_user,
            overrides=payload.get('policies'),
            initialize_balances=payload['initialize_balances'],
            as_of_date=payload.get('as_of_date'),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_POLICY_PACK_FAILED', str(exc), 400)

    return success(
        {
            'items': [policy.to_dict() for policy in policies],
            'balances': balance_result,
            'setup': leave_setup_status(
                tenant.id,
                current_user,
            ),
        },
        'Standard leave policy pack applied',
        201,
    )


@leave_bp.post('/setup/initialize-balances')
@jwt_required()
@permission_required('leave:approve')
def initialize_balances():
    try:
        payload = LeaveBalanceInitializeSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        if not can_configure_leave(current_user):
            return fail(
                'FORBIDDEN',
                'Only organization owners and HR administrators '
                'can initialize leave balances',
                403,
            )
        result = initialize_leave_balances(
            tenant.id,
            year=payload.get('year'),
            as_of_date=payload.get('as_of_date'),
            overwrite_unused=payload['overwrite_unused'],
            actor_user_id=current_user.id,
        )
        db.session.commit()
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_BALANCE_INIT_FAILED', str(exc), 400)

    return success(
        {
            **result,
            'setup': leave_setup_status(
                tenant.id,
                current_user,
            ),
        },
        'Leave balances initialized',
    )


@leave_bp.post('/setup/run-accruals')
@jwt_required()
@permission_required('leave:adjust')
def run_accruals():
    try:
        payload = LeaveAccrualRunSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        result = run_scheduled_accruals(
            as_of_date=payload.get('as_of_date'),
            tenant_id=tenant.id,
            actor=current_user,
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_ACCRUAL_FAILED', str(exc), 400)

    return success(
        result,
        'Leave allocations processed',
    )


@leave_bp.get('/types')
@jwt_required()
@permission_required('leave:create')
def list_leave_types():
    query = tenant_query(LeaveType)
    if request.args.get('include_inactive') != 'true':
        query = query.filter_by(is_active=True)
    query = query.order_by(LeaveType.name.asc())
    return success({
        'items': [
            item.to_dict()
            for item in query.all()
        ],
    })


@leave_bp.post('/types')
@jwt_required()
@permission_required('leave:approve')
def create_leave_type():
    try:
        payload = LeaveTypeCreateSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        if not can_configure_leave(current_user):
            return fail(
                'FORBIDDEN',
                'Only organization owners and HR administrators '
                'can create leave policies',
                403,
            )
        leave_type = LeaveType(
            tenant_id=tenant.id,
            **payload,
        )
        db.session.add(leave_type)
        db.session.commit()
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_TYPE_CREATE_FAILED', str(exc), 400)
    return success(
        leave_type.to_dict(),
        'Leave type created',
        201,
    )


@leave_bp.post('/requests')
@jwt_required()
@permission_required('leave:create')
def submit_leave_request():
    try:
        payload = LeaveRequestCreateSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        request_obj = create_leave_request(
            payload,
            tenant.id,
            current_user,
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_REQUEST_FAILED', str(exc), 400)
    return success(
        _serialize_request(request_obj),
        'Leave request submitted',
        201,
    )


@leave_bp.get('/requests')
@jwt_required()
@permission_required('leave:create')
def list_leave_requests():
    page, per_page = get_pagination()
    query = request_scope_query(
        current_user,
        tenant_query(LeaveRequest),
    )

    view = request.args.get('view')
    if view == 'mine':
        if not current_user.employee_profile:
            query = query.filter(false())
        else:
            query = query.filter(
                LeaveRequest.employee_id
                == current_user.employee_profile.id
            )
    elif view == 'approvals':
        query = query.filter(
            LeaveRequest.required_approver_id
            == current_user.id,
            LeaveRequest.status == 'pending',
        )

    if request.args.get('status'):
        query = query.filter(
            LeaveRequest.status == request.args['status']
        )
    if request.args.get('employee_id'):
        query = query.filter(
            LeaveRequest.employee_id
            == request.args['employee_id']
        )

    pagination = query.order_by(
        LeaveRequest.created_at.desc(),
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    data = paginated_response(pagination)
    data['items'] = [
        _serialize_request(item)
        for item in pagination.items
    ]
    return success(data)


@leave_bp.patch('/requests/<request_id>/approve')
@jwt_required()
@permission_required('leave:approve')
def approve_leave(request_id):
    leave_request = tenant_query(LeaveRequest).filter_by(
        id=request_id,
    ).first_or_404()
    employee_user_id = leave_request.employee.user_id
    if (
        not leave_request.required_approver_id
        or str(leave_request.required_approver_id) != str(current_user.id)
        or str(leave_request.requested_by_user_id) == str(current_user.id)
        or (
            employee_user_id
            and str(employee_user_id) == str(current_user.id)
        )
    ):
        return fail(
            'FORBIDDEN',
            'You cannot approve this leave request',
            403,
        )
    try:
        payload = LeaveDecisionSchema().load(
            request.get_json() or {},
        )
        leave_request = decide_leave_request(
            leave_request,
            'approved',
            current_user,
            payload.get('decision_notes'),
        )
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail(
            'LEAVE_APPROVAL_FAILED',
            getattr(err, 'messages', str(err)),
            400,
        )
    return success(
        _serialize_request(leave_request),
        'Leave request approved',
    )


@leave_bp.patch('/requests/<request_id>/reject')
@jwt_required()
@permission_required('leave:approve')
def reject_leave(request_id):
    leave_request = tenant_query(LeaveRequest).filter_by(
        id=request_id,
    ).first_or_404()
    employee_user_id = leave_request.employee.user_id
    if (
        not leave_request.required_approver_id
        or str(leave_request.required_approver_id) != str(current_user.id)
        or str(leave_request.requested_by_user_id) == str(current_user.id)
        or (
            employee_user_id
            and str(employee_user_id) == str(current_user.id)
        )
    ):
        return fail(
            'FORBIDDEN',
            'You cannot reject this leave request',
            403,
        )
    try:
        payload = LeaveDecisionSchema().load(
            request.get_json() or {},
        )
        leave_request = decide_leave_request(
            leave_request,
            'rejected',
            current_user,
            payload.get('decision_notes'),
        )
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail(
            'LEAVE_REJECTION_FAILED',
            getattr(err, 'messages', str(err)),
            400,
        )
    return success(
        _serialize_request(leave_request),
        'Leave request rejected',
    )


@leave_bp.patch('/requests/<request_id>/cancel')
@jwt_required()
@permission_required('leave:create')
def cancel_leave(request_id):
    leave_request = tenant_query(LeaveRequest).filter_by(
        id=request_id,
    ).first_or_404()
    owns_request = bool(
        current_user.employee_profile
        and str(current_user.employee_profile.id)
        == str(leave_request.employee_id)
    )
    if not owns_request and not can_configure_leave(current_user):
        return fail(
            'FORBIDDEN',
            'You cannot cancel this leave request',
            403,
        )
    try:
        payload = LeaveCancellationSchema().load(
            request.get_json() or {},
        )
        leave_request = cancel_leave_request(
            leave_request,
            current_user,
            payload.get('decision_notes'),
        )
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail(
            'LEAVE_CANCELLATION_FAILED',
            getattr(err, 'messages', str(err)),
            400,
        )
    return success(
        _serialize_request(leave_request),
        'Leave request cancelled',
    )


@leave_bp.get('/balances')
@jwt_required()
@permission_required('leave:create')
def leave_balances():
    query = balance_scope_query(
        current_user,
        tenant_query(LeaveBalance),
    )
    balance_year = request.args.get('year')
    if balance_year:
        try:
            resolved_year = int(balance_year)
        except ValueError:
            return fail(
                'VALIDATION_ERROR',
                {'year': ['Not a valid integer.']},
                422,
            )
        query = query.filter(LeaveBalance.year == resolved_year)
    elif request.args.get('include_history') != 'true':
        query = query.filter(LeaveBalance.year == date.today().year)

    if request.args.get('employee_id'):
        query = query.filter(
            LeaveBalance.employee_id
            == request.args['employee_id']
        )

    query = query.order_by(
        LeaveBalance.year.desc(),
        LeaveBalance.employee_id.asc(),
    )
    return success({
        'items': [
            balance.to_dict()
            for balance in query.all()
        ],
    })


@leave_bp.post('/balances/<balance_id>/adjustments')
@jwt_required()
@permission_required('leave:adjust')
def adjust_balance(balance_id):
    try:
        payload = LeaveBalanceAdjustmentSchema().load(
            request.get_json() or {},
        )
        tenant, error = _tenant_or_error(payload)
        if error:
            return error
        balance = LeaveBalance.query.filter_by(
            id=balance_id,
            tenant_id=tenant.id,
        ).first()
        if balance is None:
            return fail(
                'LEAVE_BALANCE_NOT_FOUND',
                'Leave balance was not found',
                404,
            )
        balance, entry = adjust_leave_balance(
            balance,
            payload['amount_days'],
            payload['reason'],
            actor=current_user,
            effective_date=payload.get('effective_date'),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('LEAVE_ADJUSTMENT_FAILED', str(exc), 400)

    return success(
        {
            'balance': balance.to_dict(),
            'ledger_entry': _serialize_ledger(entry),
        },
        'Leave balance adjusted',
    )


@leave_bp.get('/ledger')
@jwt_required()
@permission_required('leave:ledger')
def leave_ledger():
    page, per_page = get_pagination()
    query = ledger_scope_query(
        current_user,
        tenant_query(LeaveLedgerEntry),
    )

    if request.args.get('employee_id'):
        query = query.filter(
            LeaveLedgerEntry.employee_id
            == request.args['employee_id']
        )
    if request.args.get('leave_type_id'):
        query = query.filter(
            LeaveLedgerEntry.leave_type_id
            == request.args['leave_type_id']
        )
    if request.args.get('event_type'):
        query = query.filter(
            LeaveLedgerEntry.event_type
            == request.args['event_type']
        )
    if request.args.get('year'):
        try:
            resolved_year = int(request.args['year'])
        except ValueError:
            return fail(
                'VALIDATION_ERROR',
                {'year': ['Not a valid integer.']},
                422,
            )
        query = query.filter(
            LeaveLedgerEntry.year == resolved_year
        )

    pagination = query.order_by(
        LeaveLedgerEntry.effective_date.desc(),
        LeaveLedgerEntry.created_at.desc(),
    ).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    data = paginated_response(pagination)
    data['items'] = [
        _serialize_ledger(entry)
        for entry in pagination.items
    ]
    return success(data)
