from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Tenant
from app.models.base import utcnow
from app.schemas.user_schema import (
    OrganizationProvisionSchema,
    TenantCreateSchema,
    TenantMfaPolicySchema,
    TenantUpdateSchema,
)
from app.services.auth_service import register_user
from app.services.audit_service import log_event
from app.services.mfa_policy_service import (
    configure_tenant_mfa_policy,
    tenant_mfa_compliance,
    tenant_mfa_policy,
)
from app.utils.decorators import permission_required
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

tenant_bp = Blueprint('tenants', __name__, url_prefix='/tenants')


def _security_tenant(tenant_id):
    tenant = Tenant.query.filter_by(
        id=tenant_id,
        deleted_at=None,
    ).first_or_404()
    if (
        not current_user.has_role('SUPER_ADMIN')
        and str(current_user.tenant_id) != str(tenant.id)
    ):
        return None
    return tenant


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


@tenant_bp.post('/provision')
@jwt_required()
@permission_required('tenant:create')
def provision_organization():
    if not current_user.has_role('SUPER_ADMIN'):
        return fail('FORBIDDEN', 'Only platform super administrators can provision organization administrators', 403)

    try:
        payload = OrganizationProvisionSchema().load(request.get_json() or {})
        tenant = Tenant(**payload['organization'])
        db.session.add(tenant)
        db.session.flush()

        admin_payload = {
            **payload['admin'],
            'tenant_id': tenant.id,
            'roles': ['CLIENT_ADMIN'],
            'email_verified_at': utcnow(),
        }
        admin = register_user(admin_payload, actor=current_user, commit=False)
        log_event('tenant.create', 'Tenant', tenant.id, tenant_id=tenant.id)
        log_event(
            'tenant.admin_provisioned',
            'User',
            admin.id,
            tenant_id=tenant.id,
            metadata={'role': 'CLIENT_ADMIN'},
        )
        db.session.commit()
    except ValidationError as err:
        db.session.rollback()
        return fail('VALIDATION_ERROR', err.messages, 422)
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        message = 'Organization name, slug or administrator email is already in use' if isinstance(exc, IntegrityError) else str(exc)
        return fail('ORGANIZATION_PROVISION_FAILED', message, 400)
    except Exception:
        db.session.rollback()
        raise

    return success(
        {'organization': tenant.to_dict(), 'admin': admin.to_dict()},
        'Organization and administrator provisioned',
        201,
    )


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

@tenant_bp.get('/<tenant_id>/mfa-policy')
@jwt_required()
@permission_required('security:mfa_policy')
def get_tenant_mfa_policy(tenant_id):
    tenant = _security_tenant(tenant_id)
    if tenant is None:
        return fail(
            'FORBIDDEN',
            'MFA policy can only be viewed within your organization',
            403,
        )
    return success(tenant_mfa_policy(tenant))


@tenant_bp.patch('/<tenant_id>/mfa-policy')
@jwt_required()
@permission_required('security:mfa_policy')
def update_tenant_mfa_policy(tenant_id):
    tenant = _security_tenant(tenant_id)
    if tenant is None:
        return fail(
            'FORBIDDEN',
            'MFA policy can only be configured within your organization',
            403,
        )

    try:
        payload = TenantMfaPolicySchema().load(
            request.get_json(silent=True) or {}
        )
        policy = configure_tenant_mfa_policy(
            tenant,
            current_user,
            payload,
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except ValueError as exc:
        return fail('MFA_POLICY_INVALID', str(exc), 422)

    log_event(
        'security.mfa_policy_updated',
        'Tenant',
        tenant.id,
        tenant_id=tenant.id,
        actor=current_user,
        metadata={
            'mode': policy['mode'],
            'grace_days': policy['grace_days'],
            'enforcement_date': policy['enforcement_date'],
        },
    )
    db.session.commit()
    return success(policy, 'MFA policy updated')


@tenant_bp.get('/<tenant_id>/mfa-compliance')
@jwt_required()
@permission_required('security:mfa_policy')
def get_tenant_mfa_compliance(tenant_id):
    tenant = _security_tenant(tenant_id)
    if tenant is None:
        return fail(
            'FORBIDDEN',
            'MFA compliance can only be viewed within your organization',
            403,
        )
    return success(tenant_mfa_compliance(tenant))
