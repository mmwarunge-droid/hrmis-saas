from sqlalchemy import false, or_, select

from app.models import AttendanceRecord, Employee


ATTENDANCE_ADMIN_ROLES = {
    'ORGANIZATION_OWNER',
    'HR_CONSULTANT',
    'CLIENT_ADMIN',
}


def accessible_attendance_query(user, query=None):
    """Scope attendance rows to the authenticated user's legitimate view."""
    query = AttendanceRecord.query if query is None else query

    if not user:
        return query.filter(false())

    if user.has_role('SUPER_ADMIN'):
        return query

    if not user.tenant_id:
        return query.filter(false())

    query = query.filter(AttendanceRecord.tenant_id == user.tenant_id)

    if user.has_any_role(ATTENDANCE_ADMIN_ROLES):
        return query

    employee_profile = user.employee_profile
    if not employee_profile:
        return query.filter(false())

    if user.has_role('MANAGER'):
        direct_report_ids = select(Employee.id).where(
            Employee.tenant_id == user.tenant_id,
            Employee.manager_id == employee_profile.id,
            Employee.deleted_at.is_(None),
        )
        return query.filter(or_(
            AttendanceRecord.employee_id == employee_profile.id,
            AttendanceRecord.employee_id.in_(direct_report_ids),
        ))

    if user.has_role('EMPLOYEE'):
        return query.filter(
            AttendanceRecord.employee_id == employee_profile.id,
        )

    return query.filter(false())


def attendance_record_payload(record):
    payload = record.to_dict()
    employee = record.employee
    payload.update({
        'employee_name': employee.full_name if employee else None,
        'employee_number': employee.employee_number if employee else None,
        'employee_profile_photo_url': (
            employee.profile_photo_url if employee else None
        ),
    })
    return payload
