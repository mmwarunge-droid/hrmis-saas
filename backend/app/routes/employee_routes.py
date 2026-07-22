from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_

from app.extensions import db
from app.models import Department, Employee
from app.schemas.employee_schema import DepartmentSchema, EmployeeCreateSchema, EmployeeUpdateSchema
from app.services.employee_service import create_employee, soft_delete_employee, update_employee
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

employee_bp = Blueprint('employees', __name__, url_prefix='/employees')


@employee_bp.get('')
@jwt_required()
@permission_required('employee:read')
def list_employees():
    page, per_page = get_pagination()
    query = tenant_query(Employee).filter(Employee.deleted_at.is_(None))
    q = request.args.get('q')
    if q:
        like = f'%{q.lower()}%'
        query = query.filter(or_(db.func.lower(Employee.first_name).like(like), db.func.lower(Employee.last_name).like(like), db.func.lower(Employee.email).like(like), db.func.lower(Employee.employee_number).like(like)))
    if request.args.get('department_id'):
        query = query.filter(Employee.department_id == request.args['department_id'])
    if request.args.get('status'):
        query = query.filter(Employee.employment_status == request.args['status'])
    return success(paginated_response(query.order_by(Employee.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)))


@employee_bp.post('')
@jwt_required()
@permission_required('employee:create')
def create():
    try:
        payload = EmployeeCreateSchema().load(request.get_json() or {})
        requested_tenant_id = payload.pop('tenant_id', None)
        tenant_id = requested_tenant_id if current_user.has_role('SUPER_ADMIN') else current_user.tenant_id
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required for employee creation', 422)
        employee = create_employee(payload, tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except Exception as exc:
        db.session.rollback()
        return fail('EMPLOYEE_CREATE_FAILED', str(exc), 400)
    return success(employee.to_dict(), 'Employee created', 201)


@employee_bp.get('/<employee_id>')
@jwt_required()
@permission_required('employee:read')
def get_employee(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    return success(employee.to_dict())


@employee_bp.patch('/<employee_id>')
@jwt_required()
@permission_required('employee:update')
def patch_employee(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    try:
        payload = EmployeeUpdateSchema().load(request.get_json() or {})
        employee = update_employee(employee, payload)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        return fail('EMPLOYEE_UPDATE_FAILED', str(exc), 400)
    return success(employee.to_dict(), 'Employee updated')


@employee_bp.delete('/<employee_id>')
@jwt_required()
@permission_required('employee:delete')
def delete_employee(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    soft_delete_employee(employee)
    return success({}, 'Employee deleted')


@employee_bp.get('/departments')
@jwt_required()
@permission_required('employee:read')
def list_departments():
    query = tenant_query(Department).filter(Department.deleted_at.is_(None)).order_by(Department.name.asc())
    return success({'items': [department.to_dict() for department in query.all()]})


@employee_bp.post('/departments')
@jwt_required()
@permission_required('employee:create')
def create_department():
    try:
        payload = DepartmentSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    tenant_id = current_user.tenant_id
    department = Department(tenant_id=tenant_id, **payload)
    db.session.add(department)
    db.session.commit()
    return success(department.to_dict(), 'Department created', 201)
