from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import Tenant
from app.schemas.user_schema import TenantCreateSchema, TenantUpdateSchema
from app.services.audit_service import log_event
from app.utils.decorators import permission_required
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

tenant_bp = Blueprint('tenants', __name__, url_prefix='/tenants')


@tenant_bp.get('')
@jwt_required()
@permission_required('tenant:read')
def list_tenants():
    page, per_page = get_pagination()
    query = Tenant.query.filter(Tenant.deleted_at.is_(None)).order_by(Tenant.name.asc())
    q = request.args.get('q')
    if q:
        like = f'%{q.lower()}%'
        query = query.filter(db.func.lower(Tenant.name).like(like))
    return success(paginated_response(query.paginate(page=page, per_page=per_page, error_out=False)))


@tenant_bp.post('')
@jwt_required()
@permission_required('tenant:create')
def create_tenant():
    try:
        payload = TenantCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    tenant = Tenant(**payload)
    db.session.add(tenant)
    db.session.flush()
    log_event('tenant.create', 'Tenant', tenant.id, tenant_id=tenant.id)
    db.session.commit()
    return success(tenant.to_dict(), 'Tenant created', 201)


@tenant_bp.get('/<tenant_id>')
@jwt_required()
@permission_required('tenant:read')
def get_tenant(tenant_id):
    return success(Tenant.query.filter_by(id=tenant_id, deleted_at=None).first_or_404().to_dict())


@tenant_bp.patch('/<tenant_id>')
@jwt_required()
@permission_required('tenant:update')
def update_tenant(tenant_id):
    tenant = Tenant.query.filter_by(id=tenant_id, deleted_at=None).first_or_404()
    try:
        payload = TenantUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    for key, value in payload.items():
        setattr(tenant, key, value)
    log_event('tenant.update', 'Tenant', tenant.id, tenant_id=tenant.id)
    db.session.commit()
    return success(tenant.to_dict(), 'Tenant updated')
