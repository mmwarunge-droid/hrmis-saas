from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Department, Employee, JobHistory
from app.schemas.employee_schema import (
    BulkDepartmentTransferSchema,
    DepartmentArchiveSchema,
    DepartmentSchema,
    DepartmentUpdateSchema,
    EmployeeAccessProvisionSchema,
    EmployeeCreateSchema,
    EmployeeUpdateSchema,
)
from app.services.access_provisioning_service import (
    AccessProvisioningError,
    provision_employee_access,
)
from app.services.department_service import (
    archive_department,
    create_department as create_department_record,
    restore_department,
    update_department,
)
from app.services.employee_service import (
    create_employee,
    soft_delete_employee,
    transfer_employees_department,
    update_employee,
)
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

employee_bp = Blueprint('employees', __name__, url_prefix='/employees')


def _request_tenant_id(payload=None):
    if current_user.has_role('SUPER_ADMIN'):
        return (payload or {}).pop('tenant_id', None) or request.args.get('tenant_id')
    if payload is not None:
        payload.pop('tenant_id', None)
    return current_user.tenant_id


def _department_payload(department, employee_counts):
    data = department.to_dict()
    data['employee_count'] = employee_counts.get(str(department.id), 0)
    data['parent_department_name'] = department.parent.name if department.parent else None
    return data


def _apply_employee_sort(query):
    sort_key = request.args.get('sort', 'created_at')
    direction = request.args.get('direction', 'desc').lower()
    descending = direction != 'asc'

    if sort_key == 'full_name':
        columns = [Employee.last_name, Employee.first_name]
    elif sort_key == 'department_id':
        query = query.outerjoin(
            Department,
            Employee.department_id == Department.id,
        )
        columns = [Department.name, Employee.last_name, Employee.first_name]
    else:
        column = {
            'created_at': Employee.created_at,
            'employee_number': Employee.employee_number,
            'job_title': Employee.job_title,
            'work_location': Employee.work_location,
            'employment_status': Employee.employment_status,
            'hire_date': Employee.hire_date,
        }.get(sort_key, Employee.created_at)
        columns = [column, Employee.last_name, Employee.first_name]

    for column in columns:
        query = query.order_by(
            column.desc() if descending else column.asc(),
        )

    return query.order_by(Employee.id.asc())


@employee_bp.get('')
@jwt_required()
@permission_required('employee:read')
def list_employees():
    page, per_page = get_pagination()
    query = tenant_query(Employee).filter(Employee.deleted_at.is_(None))
    q = request.args.get('q')
    if q:
        like = f'%{q.strip().lower()}%'
        query = query.filter(or_(
            db.func.lower(Employee.first_name).like(like),
            db.func.lower(Employee.last_name).like(like),
            db.func.lower(Employee.email).like(like),
            db.func.lower(Employee.employee_number).like(like),
            db.func.lower(Employee.job_title).like(like),
            db.func.lower(Employee.work_location).like(like),
        ))
    if request.args.get('department_id'):
        query = query.filter(
            Employee.department_id == request.args['department_id'],
        )
    if request.args.get('status'):
        query = query.filter(
            Employee.employment_status == request.args['status'],
        )

    query = _apply_employee_sort(query)
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return success(paginated_response(pagination))


@employee_bp.get('/summary')
@jwt_required()
@permission_required('employee:read')
def employee_summary():
    employee_query = tenant_query(Employee).filter(
        Employee.deleted_at.is_(None),
    )
    status_rows = employee_query.with_entities(
        Employee.employment_status,
        func.count(Employee.id),
    ).group_by(Employee.employment_status).all()
    status_counts = {
        status: count
        for status, count in status_rows
    }
    total = sum(status_counts.values())
    active = status_counts.get('active', 0)

    work_locations = employee_query.with_entities(
        func.count(func.distinct(Employee.work_location)),
    ).filter(
        Employee.work_location.is_not(None),
        func.trim(Employee.work_location) != '',
    ).scalar() or 0

    departments = tenant_query(Department).filter(
        Department.deleted_at.is_(None),
    ).count()

    return success({
        'total': total,
        'active': active,
        'not_active': total - active,
        'work_locations': work_locations,
        'departments': departments,
        'by_status': status_counts,
    })


@employee_bp.post('')
@jwt_required()
@permission_required('employee:create')
def create():
    try:
        payload = EmployeeCreateSchema().load(request.get_json() or {})
        tenant_id = _request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required for employee creation', 422)
        employee = create_employee(payload, tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except Exception as exc:
        db.session.rollback()
        return fail('EMPLOYEE_CREATE_FAILED', str(exc), 400)
    return success(employee.to_dict(), 'Employee created', 201)


@employee_bp.get('/options')
@jwt_required()
@permission_required('employee:read')
def employee_options():
    employees = (
        tenant_query(Employee)
        .filter(Employee.deleted_at.is_(None))
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )
    return success({
        'items': [
            {
                'id': str(employee.id),
                'full_name': employee.full_name,
                'job_title': employee.job_title,
                'department_id': str(employee.department_id) if employee.department_id else None,
                'manager_id': str(employee.manager_id) if employee.manager_id else None,
                'employment_status': employee.employment_status,
            }
            for employee in employees
        ],
    })


@employee_bp.get('/org-chart')
@jwt_required()
@permission_required('employee:read')
def org_chart():
    employees = (
        tenant_query(Employee)
        .options(selectinload(Employee.department))
        .filter(
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(['active', 'probation']),
        )
        .order_by(Employee.last_name.asc(), Employee.first_name.asc())
        .all()
    )

    employees_by_id = {str(employee.id): employee for employee in employees}
    children_by_manager = {employee_id: [] for employee_id in employees_by_id}
    roots = []

    for employee in employees:
        manager_id = str(employee.manager_id) if employee.manager_id else None
        if manager_id and manager_id in employees_by_id:
            children_by_manager[manager_id].append(employee)
        else:
            roots.append(employee)

    visited = set()

    def serialize(employee, ancestors=None):
        ancestors = ancestors or set()
        employee_id = str(employee.id)
        if employee_id in ancestors:
            return None

        visited.add(employee_id)
        next_ancestors = {*ancestors, employee_id}
        children = []

        for report in children_by_manager.get(employee_id, []):
            node = serialize(report, next_ancestors)
            if node is not None:
                children.append(node)

        manager = employees_by_id.get(str(employee.manager_id)) if employee.manager_id else None
        return {
            'id': employee_id,
            'full_name': employee.full_name,
            'job_title': employee.job_title,
            'department_name': employee.department.name if employee.department else None,
            'manager_id': str(employee.manager_id) if employee.manager_id else None,
            'manager_name': manager.full_name if manager else None,
            'work_location': employee.work_location,
            'employment_status': employee.employment_status,
            'direct_report_count': len(children),
            'children': children,
        }

    tree = [node for root in roots if (node := serialize(root)) is not None]

    # Defensive fallback for legacy cyclic data: surface any unvisited people
    # instead of returning a blank chart.
    for employee in employees:
        if str(employee.id) not in visited:
            node = serialize(employee)
            if node is not None:
                tree.append(node)

    def depth(node):
        return 1 + max((depth(child) for child in node['children']), default=0)

    inactive_positions = (
        tenant_query(Employee)
        .options(selectinload(Employee.department))
        .filter(
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(['inactive', 'suspended', 'terminated']),
            Employee.job_title.is_not(None),
        )
        .order_by(Employee.job_title.asc())
        .all()
    )
    vacancies = [
        {
            'id': f'vacant:{employee.id}',
            'job_title': employee.job_title,
            'department_name': employee.department.name if employee.department else None,
            'former_employee_id': str(employee.id),
            'status': 'vacant',
        }
        for employee in inactive_positions
    ]

    return success({
        'roots': tree,
        'vacancies': vacancies,
        'meta': {
            'total': len(employees),
            'root_count': len(tree),
            'manager_count': sum(bool(children_by_manager[employee_id]) for employee_id in employees_by_id),
            'max_depth': max((depth(root) for root in tree), default=0),
        },
    })


@employee_bp.get('/departments')
@jwt_required()
@permission_required('employee:read')
def list_departments():
    tenant_id = _request_tenant_id()
    if not tenant_id:
        return fail('TENANT_REQUIRED', 'tenant_id is required', 422)

    include_archived = request.args.get('include_archived', '').lower() in {'1', 'true', 'yes'}
    query = Department.query.options(
        selectinload(Department.parent),
        selectinload(Department.head),
    ).filter(Department.tenant_id == tenant_id)
    if not include_archived:
        query = query.filter(Department.deleted_at.is_(None))

    count_rows = (
        db.session.query(Employee.department_id, func.count(Employee.id))
        .filter(
            Employee.tenant_id == tenant_id,
            Employee.deleted_at.is_(None),
            Employee.employment_status.in_(['active', 'probation']),
            Employee.department_id.is_not(None),
        )
        .group_by(Employee.department_id)
        .all()
    )
    employee_counts = {str(department_id): count for department_id, count in count_rows}
    departments = query.order_by(Department.deleted_at.asc(), Department.name.asc()).all()
    return success({
        'items': [
            _department_payload(department, employee_counts)
            for department in departments
        ],
    })


@employee_bp.post('/departments')
@jwt_required()
@permission_required('employee:create')
def create_department():
    try:
        payload = DepartmentSchema().load(request.get_json() or {})
        tenant_id = _request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required', 422)
        department = create_department_record(payload, tenant_id)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except IntegrityError:
        db.session.rollback()
        return fail('DEPARTMENT_CONFLICT', 'Department name or code already exists', 409)
    except ValueError as exc:
        db.session.rollback()
        return fail('DEPARTMENT_CREATE_FAILED', str(exc), 400)
    return success(department.to_dict(), 'Department created', 201)


@employee_bp.patch('/departments/<department_id>')
@jwt_required()
@permission_required('employee:update')
def patch_department(department_id):
    try:
        payload = DepartmentUpdateSchema().load(request.get_json() or {})
        tenant_id = _request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required', 422)
        department = Department.query.filter_by(
            id=department_id,
            tenant_id=tenant_id,
            deleted_at=None,
        ).first_or_404()
        department = update_department(department, payload)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except IntegrityError:
        db.session.rollback()
        return fail('DEPARTMENT_CONFLICT', 'Department name or code already exists', 409)
    except ValueError as exc:
        db.session.rollback()
        return fail('DEPARTMENT_UPDATE_FAILED', str(exc), 400)
    return success(department.to_dict(), 'Department updated')


@employee_bp.post('/departments/<department_id>/archive')
@jwt_required()
@permission_required('employee:update')
def archive_department_route(department_id):
    raw_payload = request.get_json() or {}
    try:
        payload = DepartmentArchiveSchema().load(raw_payload)
        tenant_id = _request_tenant_id()
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required', 422)
        department = Department.query.filter_by(
            id=department_id,
            tenant_id=tenant_id,
        ).first_or_404()
        department, changed = archive_department(
            department,
            payload.get('replacement_department_id'),
            'replacement_department_id' in raw_payload,
            payload['effective_date'],
            payload['reason'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('DEPARTMENT_ARCHIVE_FAILED', str(exc), 400)
    return success(
        {
            'department': department.to_dict(),
            'employees_reassigned': len(changed),
        },
        'Department archived',
    )


@employee_bp.post('/departments/<department_id>/restore')
@jwt_required()
@permission_required('employee:update')
def restore_department_route(department_id):
    tenant_id = _request_tenant_id()
    if not tenant_id:
        return fail('TENANT_REQUIRED', 'tenant_id is required', 422)
    department = Department.query.filter_by(
        id=department_id,
        tenant_id=tenant_id,
    ).first_or_404()
    try:
        department = restore_department(department)
    except IntegrityError:
        db.session.rollback()
        return fail('DEPARTMENT_CONFLICT', 'An active department uses this name or code', 409)
    except ValueError as exc:
        db.session.rollback()
        return fail('DEPARTMENT_RESTORE_FAILED', str(exc), 400)
    return success(department.to_dict(), 'Department restored')


@employee_bp.post('/bulk-department-transfer')
@jwt_required()
@permission_required('employee:update')
def bulk_department_transfer():
    try:
        payload = BulkDepartmentTransferSchema().load(request.get_json() or {})
        tenant_id = _request_tenant_id(payload)
        if not tenant_id:
            return fail('TENANT_REQUIRED', 'tenant_id is required', 422)

        employee_ids = list(dict.fromkeys(payload['employee_ids']))
        employees = Employee.query.filter(
            Employee.tenant_id == tenant_id,
            Employee.id.in_(employee_ids),
            Employee.deleted_at.is_(None),
        ).all()
        found_ids = {str(employee.id) for employee in employees}
        missing_ids = [str(employee_id) for employee_id in employee_ids if str(employee_id) not in found_ids]
        if missing_ids:
            return fail(
                'EMPLOYEE_NOT_FOUND',
                f'{len(missing_ids)} employee record(s) were not found in this tenant',
                404,
            )

        changed = transfer_employees_department(
            employees,
            payload['department_id'],
            payload['effective_date'],
            payload['reason'],
            tenant_id,
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('DEPARTMENT_TRANSFER_FAILED', str(exc), 400)

    return success(
        {
            'updated_count': len(changed),
            'items': [employee.to_dict() for employee in changed],
        },
        f'{len(changed)} employee(s) transferred',
    )


@employee_bp.post('/<employee_id>/provision-access')
@jwt_required()
@permission_required('user:create', 'employee:update')
def provision_access(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    try:
        payload = EmployeeAccessProvisionSchema().load(request.get_json() or {})
        user = provision_employee_access(employee, payload, current_user)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except AccessProvisioningError as exc:
        db.session.rollback()
        return fail(exc.code, str(exc), exc.status_code)
    except IntegrityError:
        db.session.rollback()
        return fail(
            'ACCESS_PROVISION_CONFLICT',
            'A user account with this email or employee link already exists',
            409,
        )
    except ValueError as exc:
        db.session.rollback()
        return fail('ACCESS_PROVISION_FAILED', str(exc), 400)
    except Exception:
        db.session.rollback()
        raise

    return success(
        {
            'user': user.to_dict(),
            'employee': employee.to_dict(),
        },
        'Employee access provisioned',
        201,
    )


@employee_bp.get('/<employee_id>')
@jwt_required()
@permission_required('employee:read')
def get_employee(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    return success(employee.to_dict())


@employee_bp.get('/<employee_id>/job-history')
@jwt_required()
@permission_required('employee:read')
def employee_job_history(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    history = (
        JobHistory.query.options(
            selectinload(JobHistory.department),
            selectinload(JobHistory.manager),
        )
        .filter_by(tenant_id=employee.tenant_id, employee_id=employee.id)
        .order_by(JobHistory.start_date.desc(), JobHistory.created_at.desc())
        .all()
    )
    return success({'items': [item.to_dict() for item in history]})


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
        db.session.rollback()
        return fail('EMPLOYEE_UPDATE_FAILED', str(exc), 400)
    return success(employee.to_dict(), 'Employee updated')


@employee_bp.delete('/<employee_id>')
@jwt_required()
@permission_required('employee:delete')
def delete_employee(employee_id):
    employee = tenant_query(Employee).filter_by(id=employee_id, deleted_at=None).first_or_404()
    soft_delete_employee(employee)
    return success({}, 'Employee deleted')
