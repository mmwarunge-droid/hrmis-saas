from datetime import date, timedelta

from flask import Blueprint
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Document, Employee, LeaveRequest
from app.utils.decorators import permission_required, tenant_query
from app.utils.response import success

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.get('/summary')
@jwt_required()
@permission_required('dashboard:read')
def summary():
    employees = tenant_query(Employee).filter(Employee.deleted_at.is_(None)).count()
    documents = tenant_query(Document).filter(Document.deleted_at.is_(None)).count()
    pending_leave = tenant_query(LeaveRequest).filter_by(status='pending').count()
    return success({'employees': employees, 'documents': documents, 'pending_leave_requests': pending_leave})


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
    rows = tenant_query(LeaveRequest).with_entities(LeaveRequest.status, db.func.count(LeaveRequest.id)).group_by(LeaveRequest.status).all()
    return success({'by_status': {status: count for status, count in rows}})
