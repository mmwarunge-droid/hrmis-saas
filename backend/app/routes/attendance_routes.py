from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import case, func, or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import AttendanceRecord, Employee
from app.models.base import utcnow
from app.services.attendance_service import (
    accessible_attendance_query,
    attendance_record_payload,
)
from app.services.audit_service import log_event
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination
from app.utils.response import fail, success

attendance_bp = Blueprint('attendance', __name__, url_prefix='/attendance')


def _parse_date_arg(name):
    value = request.args.get(name)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f'{name} must use YYYY-MM-DD format') from exc


def _base_attendance_query():
    return (
        accessible_attendance_query(
            current_user,
            tenant_query(AttendanceRecord),
        )
        .join(Employee, AttendanceRecord.employee_id == Employee.id)
    )


def _apply_attendance_filters(query):
    employee_id = request.args.get('employee_id')
    if employee_id:
        query = query.filter(AttendanceRecord.employee_id == employee_id)

    exact_date = _parse_date_arg('date')
    date_from = _parse_date_arg('date_from')
    date_to = _parse_date_arg('date_to')
    if date_from and date_to and date_from > date_to:
        raise ValueError('date_from cannot be after date_to')
    if exact_date:
        query = query.filter(AttendanceRecord.work_date == exact_date)
    if date_from:
        query = query.filter(AttendanceRecord.work_date >= date_from)
    if date_to:
        query = query.filter(AttendanceRecord.work_date <= date_to)

    status = request.args.get('status')
    if status == 'complete':
        query = query.filter(
            AttendanceRecord.check_in_at.is_not(None),
            AttendanceRecord.check_out_at.is_not(None),
        )
    elif status == 'in_progress':
        query = query.filter(
            AttendanceRecord.check_in_at.is_not(None),
            AttendanceRecord.check_out_at.is_(None),
        )
    elif status:
        raise ValueError('status must be complete or in_progress')

    q = request.args.get('q')
    if q:
        like = f'%{q.strip().lower()}%'
        query = query.filter(or_(
            func.lower(Employee.first_name).like(like),
            func.lower(Employee.last_name).like(like),
            func.lower(
                Employee.first_name + ' ' + Employee.last_name,
            ).like(like),
            func.lower(Employee.email).like(like),
            func.lower(Employee.employee_number).like(like),
        ))

    return query


def _apply_attendance_sort(query):
    sort_key = request.args.get('sort', 'work_date')
    direction = request.args.get('direction', 'desc').lower()
    descending = direction != 'asc'

    if sort_key == 'employee_name':
        columns = [Employee.last_name, Employee.first_name]
    elif sort_key == 'status':
        status_order = case(
            (AttendanceRecord.check_out_at.is_not(None), 2),
            (AttendanceRecord.check_in_at.is_not(None), 1),
            else_=0,
        )
        columns = [status_order, AttendanceRecord.work_date]
    else:
        column = {
            'work_date': AttendanceRecord.work_date,
            'check_in_at': AttendanceRecord.check_in_at,
            'check_out_at': AttendanceRecord.check_out_at,
            'source': AttendanceRecord.source,
        }.get(sort_key, AttendanceRecord.work_date)
        columns = [column]

    for column in columns:
        query = query.order_by(
            column.desc() if descending else column.asc(),
        )

    return query.order_by(AttendanceRecord.id.asc())


@attendance_bp.get('')
@jwt_required()
@permission_required('attendance:read')
def list_attendance():
    page, per_page = get_pagination()
    try:
        query = _apply_attendance_filters(_base_attendance_query())
    except ValueError as exc:
        return fail('VALIDATION_ERROR', str(exc), 422)

    pagination = (
        _apply_attendance_sort(query)
        .options(joinedload(AttendanceRecord.employee))
        .paginate(page=page, per_page=per_page, error_out=False)
    )
    return success({
        'items': [
            attendance_record_payload(record)
            for record in pagination.items
        ],
        'meta': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        },
    })


@attendance_bp.get('/summary')
@jwt_required()
@permission_required('attendance:read')
def attendance_summary():
    try:
        query = _apply_attendance_filters(_base_attendance_query())
    except ValueError as exc:
        return fail('VALIDATION_ERROR', str(exc), 422)

    today = date.today()
    total = query.with_entities(func.count(AttendanceRecord.id)).scalar() or 0
    completed = query.filter(
        AttendanceRecord.check_in_at.is_not(None),
        AttendanceRecord.check_out_at.is_not(None),
    ).with_entities(func.count(AttendanceRecord.id)).scalar() or 0
    open_sessions = query.filter(
        AttendanceRecord.check_in_at.is_not(None),
        AttendanceRecord.check_out_at.is_(None),
    ).with_entities(func.count(AttendanceRecord.id)).scalar() or 0
    today_query = query.filter(AttendanceRecord.work_date == today)
    today_checked_in = today_query.filter(
        AttendanceRecord.check_in_at.is_not(None),
    ).with_entities(func.count(AttendanceRecord.id)).scalar() or 0
    today_completed = today_query.filter(
        AttendanceRecord.check_out_at.is_not(None),
    ).with_entities(func.count(AttendanceRecord.id)).scalar() or 0
    today_open = today_query.filter(
        AttendanceRecord.check_in_at.is_not(None),
        AttendanceRecord.check_out_at.is_(None),
    ).with_entities(func.count(AttendanceRecord.id)).scalar() or 0

    return success({
        'total': total,
        'completed': completed,
        'open_sessions': open_sessions,
        'today_checked_in': today_checked_in,
        'today_completed': today_completed,
        'today_open': today_open,
    })


def _current_employee():
    if not current_user.employee_profile:
        raise ValueError(
            'The current user is not linked to an employee profile',
        )
    return current_user.employee_profile


@attendance_bp.get('/me/today')
@jwt_required()
@permission_required('attendance:write')
def my_attendance_today():
    try:
        employee = _current_employee()
    except ValueError as exc:
        return fail('ATTENDANCE_FAILED', str(exc), 400)

    record = AttendanceRecord.query.filter_by(
        tenant_id=current_user.tenant_id,
        employee_id=employee.id,
        work_date=date.today(),
    ).first()
    return success(record.to_dict() if record else None)


@attendance_bp.post('/check-in')
@jwt_required()
@permission_required('attendance:write')
def check_in():
    try:
        employee = _current_employee()
        today = date.today()
        record = AttendanceRecord.query.filter_by(
            tenant_id=current_user.tenant_id,
            employee_id=employee.id,
            work_date=today,
        ).first()
        if not record:
            record = AttendanceRecord(
                tenant_id=current_user.tenant_id,
                employee_id=employee.id,
                work_date=today,
            )
            db.session.add(record)
        if record.check_in_at:
            return fail(
                'ALREADY_CHECKED_IN',
                'Check-in already exists for today',
                409,
            )
        record.check_in_at = utcnow()
        log_event(
            'attendance.check_in',
            'AttendanceRecord',
            record.id,
            tenant_id=current_user.tenant_id,
        )
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
        record = AttendanceRecord.query.filter_by(
            tenant_id=current_user.tenant_id,
            employee_id=employee.id,
            work_date=today,
        ).first()
        if not record or not record.check_in_at:
            return fail(
                'CHECK_IN_REQUIRED',
                'You must check in before checking out',
                409,
            )
        if record.check_out_at:
            return fail(
                'ALREADY_CHECKED_OUT',
                'Check-out already exists for today',
                409,
            )
        record.check_out_at = utcnow()
        log_event(
            'attendance.check_out',
            'AttendanceRecord',
            record.id,
            tenant_id=current_user.tenant_id,
        )
        db.session.commit()
    except ValueError as exc:
        return fail('ATTENDANCE_FAILED', str(exc), 400)
    return success(record.to_dict(), 'Checked out')
