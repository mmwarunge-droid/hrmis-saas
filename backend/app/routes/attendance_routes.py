from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required

from app.extensions import db
from app.models import AttendanceRecord
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


@attendance_bp.get('')
@jwt_required()
@permission_required('attendance:read')
def list_attendance():
    page, per_page = get_pagination()
    query = tenant_query(AttendanceRecord)
    if request.args.get('employee_id'):
        query = query.filter(AttendanceRecord.employee_id == request.args['employee_id'])
    if request.args.get('date'):
        query = query.filter(AttendanceRecord.work_date == request.args['date'])
    return success(paginated_response(query.order_by(AttendanceRecord.work_date.desc()).paginate(page=page, per_page=per_page, error_out=False)))


def _current_employee():
    if not current_user.employee_profile:
        raise ValueError('The current user is not linked to an employee profile')
    return current_user.employee_profile


@attendance_bp.post('/check-in')
@jwt_required()
@permission_required('attendance:write')
def check_in():
    try:
        employee = _current_employee()
        today = date.today()
        record = AttendanceRecord.query.filter_by(tenant_id=current_user.tenant_id, employee_id=employee.id, work_date=today).first()
        if not record:
            record = AttendanceRecord(tenant_id=current_user.tenant_id, employee_id=employee.id, work_date=today)
            db.session.add(record)
        if record.check_in_at:
            return fail('ALREADY_CHECKED_IN', 'Check-in already exists for today', 409)
        record.check_in_at = utcnow()
        log_event('attendance.check_in', 'AttendanceRecord', record.id, tenant_id=current_user.tenant_id)
        db.session.commit()
    except ValueError as exc:
        return fail('ATTENDANCE_FAILED', str(exc), 400)
    return success(record.to_dict(), 'Checked in')


@attendance_bp.post('/check-out')
@jwt_required()
@permission_required('attendance:write')
def check_out():
    try:
        employee = _current_employee()
        today = date.today()
        record = AttendanceRecord.query.filter_by(tenant_id=current_user.tenant_id, employee_id=employee.id, work_date=today).first()
        if not record or not record.check_in_at:
            return fail('CHECK_IN_REQUIRED', 'You must check in before checking out', 409)
        if record.check_out_at:
            return fail('ALREADY_CHECKED_OUT', 'Check-out already exists for today', 409)
        record.check_out_at = utcnow()
        log_event('attendance.check_out', 'AttendanceRecord', record.id, tenant_id=current_user.tenant_id)
        db.session.commit()
    except ValueError as exc:
        return fail('ATTENDANCE_FAILED', str(exc), 400)
    return success(record.to_dict(), 'Checked out')
