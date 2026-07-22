from app.extensions import db
from app.models import Employee, LeaveBalance, LeaveRequest, LeaveType
from app.models.base import utcnow
from app.services.audit_service import log_event


def create_leave_request(payload, tenant_id):
    employee = Employee.query.filter_by(id=payload['employee_id'], tenant_id=tenant_id, deleted_at=None).first()
    leave_type = LeaveType.query.filter_by(id=payload['leave_type_id'], tenant_id=tenant_id, is_active=True).first()
    if not employee:
        raise ValueError('employee_id is invalid for this tenant')
    if not leave_type:
        raise ValueError('leave_type_id is invalid for this tenant')
    request = LeaveRequest(tenant_id=tenant_id, **payload)
    db.session.add(request)
    db.session.flush()
    log_event('leave.request', 'LeaveRequest', request.id, tenant_id=tenant_id)
    db.session.commit()
    return request


def decide_leave_request(leave_request, status, approver_id, notes=None):
    if leave_request.status != 'pending':
        raise ValueError('Only pending leave requests can be decided')
    leave_request.status = status
    leave_request.approver_id = approver_id
    leave_request.decision_notes = notes
    leave_request.decided_at = utcnow()
    if status == 'approved':
        balance = LeaveBalance.query.filter_by(
            tenant_id=leave_request.tenant_id,
            employee_id=leave_request.employee_id,
            leave_type_id=leave_request.leave_type_id,
            year=leave_request.start_date.year,
        ).first()
        if balance:
            balance.used_days = (balance.used_days or 0) + leave_request.total_days
            balance.balance_days = (balance.balance_days or 0) - leave_request.total_days
    log_event(f'leave.{status}', 'LeaveRequest', leave_request.id, tenant_id=leave_request.tenant_id)
    db.session.commit()
    return leave_request
