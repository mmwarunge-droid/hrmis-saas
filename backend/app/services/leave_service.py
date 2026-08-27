from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import false, or_

from app.extensions import db
from app.models import Employee, LeaveRequest, LeaveType, Tenant, User
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.services.leave_accrual_service import (
    approve_request_balance,
    assert_balance_available,
    record_request_cancelled,
    reserve_request_balance,
    restore_request_balance,
)
from app.services.notification_service import create_notification
from app.services.leave_policy_service import (
    SUBMIT_FOR_OTHERS_ROLES,
    can_configure_leave,
    find_fallback_owner,
)


def calculate_working_days(start_date, end_date):
    if end_date < start_date:
        raise ValueError('end_date must be on or after start_date')

    total = 0
    current = start_date
    while current <= end_date:
        if current.weekday() < 5:
            total += 1
        current += timedelta(days=1)

    if total <= 0:
        raise ValueError(
            'The selected period does not contain a working day'
        )
    return Decimal(total)


def _employee_user(employee):
    if not employee.user_id:
        return None

    return User.query.filter(
        User.id == employee.user_id,
        User.tenant_id == employee.tenant_id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()


def _manager_approver(employee):
    manager = employee.manager
    if not manager or not manager.user_id:
        return None
    return User.query.filter(
        User.id == manager.user_id,
        User.tenant_id == employee.tenant_id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()


def resolve_required_approver(employee, tenant, requester_user):
    employee_user = _employee_user(employee)
    requester_is_employee = bool(
        requester_user.employee_profile
        and str(requester_user.employee_profile.id)
        == str(employee.id)
    )
    requester_roles = set(
        employee_user.role_names
        if employee_user
        else (
            requester_user.role_names
            if requester_is_employee
            else []
        )
    )

    if 'ORGANIZATION_OWNER' in requester_roles:
        approver = tenant.leave_alternate_approver
        route = 'owner_to_alternate'
    elif requester_roles.intersection(
        {'CLIENT_ADMIN', 'HR_CONSULTANT'}
    ):
        approver = tenant.organization_owner
        route = 'hr_to_owner'
    else:
        approver = _manager_approver(employee)
        route = (
            'manager_to_manager'
            if 'MANAGER' in requester_roles
            else 'employee_to_manager'
        )
        if approver is None:
            approver = tenant.organization_owner
            route = (
                'manager_to_owner'
                if 'MANAGER' in requester_roles
                else 'employee_to_owner'
            )

    requester_id = (
        employee_user.id
        if employee_user
        else requester_user.id
    )
    if approver and str(approver.id) == str(requester_id):
        approver = find_fallback_owner(
            employee.tenant_id,
            exclude_user_id=requester_id,
        )
        route = 'self_approval_fallback'

    if not approver:
        raise ValueError(
            'No independent leave approver is configured. '
            'Assign a manager, organization owner or alternate approver.'
        )
    return approver, route


def create_leave_request(payload, tenant_id, actor):
    employee_id = payload.pop('employee_id', None)
    if employee_id is None and actor.employee_profile:
        employee_id = actor.employee_profile.id

    employee = Employee.query.filter_by(
        id=employee_id,
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()
    leave_type = LeaveType.query.filter_by(
        id=payload['leave_type_id'],
        tenant_id=tenant_id,
        is_active=True,
    ).first()
    tenant = db.session.get(Tenant, tenant_id)

    if not employee:
        raise ValueError(
            'employee_id is invalid for this organization'
        )
    if not leave_type:
        raise ValueError(
            'leave_type_id is invalid for this organization'
        )
    if not tenant or tenant.deleted_at is not None:
        raise ValueError('Organization was not found')

    can_submit_for_others = actor.has_any_role(
        SUBMIT_FOR_OTHERS_ROLES
    )
    if (
        not can_submit_for_others
        and (
            not actor.employee_profile
            or str(actor.employee_profile.id) != str(employee.id)
        )
    ):
        raise ValueError(
            'Users may only submit leave for their own '
            'employee profile'
        )

    start_date = payload['start_date']
    end_date = payload['end_date']
    total_days = calculate_working_days(
        start_date,
        end_date,
    )

    overlap = LeaveRequest.query.filter(
        LeaveRequest.tenant_id == tenant_id,
        LeaveRequest.employee_id == employee.id,
        LeaveRequest.status.in_(['pending', 'approved']),
        LeaveRequest.start_date <= end_date,
        LeaveRequest.end_date >= start_date,
    ).first()
    if overlap:
        raise ValueError(
            'The employee already has an overlapping leave request'
        )

    assert_balance_available(
        employee,
        leave_type,
        start_date,
        total_days,
    )

    approver = None
    approval_route = 'automatic'
    status = 'approved'
    if leave_type.requires_approval:
        approver, approval_route = resolve_required_approver(
            employee,
            tenant,
            actor,
        )
        status = 'pending'

    request_obj = LeaveRequest(
        tenant_id=tenant_id,
        employee_id=employee.id,
        leave_type_id=leave_type.id,
        start_date=start_date,
        end_date=end_date,
        total_days=total_days,
        reason=payload.get('reason'),
        status=status,
        requested_by_user_id=actor.id,
        required_approver_id=(
            approver.id
            if approver
            else None
        ),
        approval_route=approval_route,
    )
    db.session.add(request_obj)
    db.session.flush()

    if status == 'pending':
        reserve_request_balance(
            request_obj,
            actor_user_id=actor.id,
        )
    else:
        request_obj.decided_at = utcnow()
        approve_request_balance(
            request_obj,
            actor_user_id=actor.id,
        )

    log_event(
        'leave.request',
        'LeaveRequest',
        request_obj.id,
        tenant_id=tenant_id,
        metadata={
            'employee_id': str(employee.id),
            'required_approver_id': (
                str(approver.id)
                if approver
                else None
            ),
            'approval_route': approval_route,
            'total_days': float(total_days),
            'balance_reserved': status == 'pending',
        },
    )
    if approver:
        create_notification(
            tenant_id=tenant_id,
            user_id=approver.id,
            title=f'{employee.full_name} requested time off',
            body=(
                f'{leave_type.name}: {start_date.isoformat()} to '
                f'{end_date.isoformat()} ({float(total_days):g} days).'
            ),
            notification_type='leave_approval',
            priority='high',
            action_url='/leave',
            metadata={'leave_request_id': str(request_obj.id)},
        )
    db.session.commit()
    return request_obj


def decide_leave_request(
    leave_request,
    status,
    actor,
    notes=None,
):
    if status not in {'approved', 'rejected'}:
        raise ValueError('Unsupported leave decision')
    if leave_request.status != 'pending':
        raise ValueError(
            'Only pending leave requests can be decided'
        )

    employee_user_id = leave_request.employee.user_id
    if (
        str(leave_request.requested_by_user_id) == str(actor.id)
        or (
            employee_user_id
            and str(employee_user_id) == str(actor.id)
        )
    ):
        raise ValueError(
            'A user cannot approve or reject their own leave request'
        )

    if (
        not leave_request.required_approver_id
        or str(leave_request.required_approver_id) != str(actor.id)
    ):
        raise ValueError(
            'This leave request is assigned to another approver'
        )

    if status == 'approved':
        approve_request_balance(
            leave_request,
            actor_user_id=actor.id,
        )
    else:
        restore_request_balance(
            leave_request,
            actor_user_id=actor.id,
            reason='rejected',
        )

    leave_request.status = status
    leave_request.approver_id = actor.id
    leave_request.decision_notes = notes
    leave_request.decided_at = utcnow()

    log_event(
        f'leave.{status}',
        'LeaveRequest',
        leave_request.id,
        tenant_id=leave_request.tenant_id,
        metadata={
            'required_approver_id': str(
                leave_request.required_approver_id
            ),
        },
    )
    recipient_id = (
        leave_request.employee.user_id
        or leave_request.requested_by_user_id
    )
    if recipient_id and str(recipient_id) != str(actor.id):
        create_notification(
            tenant_id=leave_request.tenant_id,
            user_id=recipient_id,
            title=f'Time-off request {status}',
            body=(
                f'{leave_request.leave_type.name}: '
                f'{leave_request.start_date.isoformat()} to '
                f'{leave_request.end_date.isoformat()}.'
            ),
            notification_type='leave_decision',
            priority='normal',
            action_url='/leave',
            metadata={'leave_request_id': str(leave_request.id)},
        )
    db.session.commit()
    return leave_request


def cancel_leave_request(leave_request, actor, notes=None):
    if leave_request.status not in {'pending', 'approved'}:
        raise ValueError(
            'Only pending or future approved requests can be cancelled'
        )

    owns_request = bool(
        actor.employee_profile
        and str(actor.employee_profile.id)
        == str(leave_request.employee_id)
    )
    if not owns_request and not can_configure_leave(actor):
        raise ValueError(
            'Users may only cancel their own leave requests'
        )
    if (
        leave_request.status == 'approved'
        and leave_request.start_date <= date.today()
    ):
        raise ValueError(
            'Approved leave can only be cancelled before its start date'
        )

    restore_request_balance(
        leave_request,
        actor_user_id=actor.id,
        reason='cancelled',
    )
    record_request_cancelled(
        leave_request,
        actor_user_id=actor.id,
        notes=notes,
    )
    leave_request.status = 'cancelled'
    leave_request.approver_id = actor.id
    leave_request.decision_notes = notes
    leave_request.decided_at = utcnow()

    log_event(
        'leave.cancelled',
        'LeaveRequest',
        leave_request.id,
        tenant_id=leave_request.tenant_id,
    )
    db.session.commit()
    return leave_request


def request_scope_query(user, query):
    if user.has_any_role(
        {
            'SUPER_ADMIN',
            'CLIENT_ADMIN',
            'HR_CONSULTANT',
            'ORGANIZATION_OWNER',
        }
    ):
        return query

    if not user.employee_profile:
        return query.filter(false())

    if user.has_role('MANAGER'):
        return query.filter(
            or_(
                LeaveRequest.employee_id
                == user.employee_profile.id,
                LeaveRequest.required_approver_id == user.id,
            )
        )

    return query.filter(
        LeaveRequest.employee_id
        == user.employee_profile.id
    )
