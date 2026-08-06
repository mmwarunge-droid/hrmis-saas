from datetime import date, timedelta

from flask import Blueprint
from flask_jwt_extended import current_user, jwt_required

from app.extensions import db
from app.models import Document, Employee, LeaveRequest
from app.services.goal_service import goal_summary
from app.services.leave_service import request_scope_query
from app.utils.decorators import permission_required, tenant_query
from app.utils.response import success


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


def _upcoming_leave_payload(leave_request):
    data = leave_request.to_dict()
    data['employee_name'] = leave_request.employee.full_name
    data['employee_profile_photo_url'] = (
        leave_request.employee.profile_photo_url
    )
    return data


@dashboard_bp.get('/summary')
@jwt_required()
@permission_required('dashboard:read')
def summary():
    employee_query = tenant_query(Employee).filter(
        Employee.deleted_at.is_(None),
    )
    status_rows = employee_query.with_entities(
        Employee.employment_status,
        db.func.count(Employee.id),
    ).group_by(Employee.employment_status).all()
    status_counts = {
        status: count
        for status, count in status_rows
    }
    employee_total = sum(status_counts.values())
    active_employees = status_counts.get('active', 0)

    recent_hires = employee_query.filter(
        Employee.hire_date.is_not(None),
    ).order_by(
        Employee.hire_date.desc(),
        Employee.created_at.desc(),
    ).limit(5).all()

    leave_query = request_scope_query(
        current_user,
        tenant_query(LeaveRequest),
    )
    upcoming_leave = leave_query.filter(
        LeaveRequest.status == 'approved',
        LeaveRequest.end_date >= date.today(),
    ).order_by(
        LeaveRequest.start_date.asc(),
        LeaveRequest.end_date.asc(),
    ).limit(5).all()

    documents = tenant_query(Document).filter(
        Document.deleted_at.is_(None),
    ).count()
    pending_leave = leave_query.filter_by(status='pending').count()

    people_health = (
        round((active_employees / employee_total) * 100)
        if employee_total
        else 0
    )

    return success({
        'employees': employee_total,
        'active_employees': active_employees,
        'inactive_employees': employee_total - active_employees,
        'employee_statuses': status_counts,
        'people_health_percent': people_health,
        'documents': documents,
        'pending_leave_requests': pending_leave,
        'recent_hires': [employee.to_dict() for employee in recent_hires],
        'goals': goal_summary(current_user),
        'upcoming_leave': [
            _upcoming_leave_payload(item)
            for item in upcoming_leave
        ],
    })


@dashboard_bp.get('/compliance-alerts')
@jwt_required()
@permission_required('dashboard:read')
def compliance_alerts():
    soon = date.today() + timedelta(days=30)
    expiring_docs = tenant_query(Document).filter(Document.deleted_at.is_(None), Document.expiry_date.isnot(None), Document.expiry_date <= soon).all()
    missing_contracts = tenant_query(Employee).filter(Employee.deleted_at.is_(None)).outerjoin(Document, db.and_(Document.employee_id == Employee.id, Document.document_type == 'contract', Document.deleted_at.is_(None))).filter(Document.id.is_(None)).all()
    return success({'expiring_documents': [doc.to_dict() for doc in expiring_docs], 'employees_missing_contracts': [employee.to_dict() for employee in missing_contracts]})


@dashboard_bp.get('/leave-summary')
@jwt_required()
@permission_required('dashboard:read')
def leave_summary():
    rows = request_scope_query(
        current_user,
        tenant_query(LeaveRequest),
    ).with_entities(
        LeaveRequest.status,
        db.func.count(LeaveRequest.id),
    ).group_by(LeaveRequest.status).all()
    return success({
        'by_status': {
            status: count
            for status, count in rows
        },
    })
