from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AccountToken, Role, Tenant, User, UserRole
from app.models.base import utcnow
from app.schemas.user_schema import (
    OrganizationProvisionSchema,
    TenantCreateSchema,
    TenantMfaPolicySchema,
    TenantUpdateSchema,
)
from app.services.account_recovery_service import (
    issue_account_token,
    send_account_invitation_email,
)
from app.services.auth_service import register_invited_user
from app.services.audit_service import log_event
from app.services.mfa_policy_service import (
    configure_tenant_mfa_policy,
    tenant_mfa_compliance,
    tenant_mfa_policy,
)
from app.services.session_service import revoke_all_user_sessions
from app.utils.decorators import permission_required
from app.utils.email import EmailDeliveryError
from app.utils.pagination import get_pagination
from app.utils.response import fail, success

tenant_bp = Blueprint('tenants', __name__, url_prefix='/tenants')


def _tenant_scope_query():
    query = Tenant.query.filter(Tenant.deleted_at.is_(None))
    if current_user.has_role('SUPER_ADMIN'):
        return query
    return query.filter(Tenant.id == current_user.tenant_id)


def _accessible_tenant(tenant_id):
    return _tenant_scope_query().filter(Tenant.id == tenant_id).first_or_404()


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


def _tenant_user_count_subquery():
    return (
        db.session.query(db.func.count(User.id))
        .filter(
            User.tenant_id == Tenant.id,
            User.deleted_at.is_(None),
        )
        .correlate(Tenant)
        .scalar_subquery()
    )


def _tenant_admin_count_subquery():
    return (
        db.session.query(db.func.count(db.func.distinct(User.id)))
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.tenant_id == Tenant.id,
            User.deleted_at.is_(None),
            Role.name == 'CLIENT_ADMIN',
        )
        .correlate(Tenant)
        .scalar_subquery()
    )


def _apply_tenant_filters(query):
    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(
            or_(
                db.func.lower(Tenant.name).like(like),
                db.func.lower(Tenant.slug).like(like),
                db.func.lower(Tenant.legal_name).like(like),
                db.func.lower(Tenant.country).like(like),
                db.func.lower(Tenant.industry).like(like),
                db.func.lower(Tenant.compliance_region).like(like),
            )
        )

    status = request.args.get('status', '').strip().lower()
    if status in {'active', 'suspended', 'archived'}:
        query = query.filter(Tenant.status == status)

    country = request.args.get('country', '').strip().lower()
    if country:
        query = query.filter(db.func.lower(Tenant.country) == country)

    return query


def _apply_tenant_sort(query, user_count, admin_count):
    sort = request.args.get('sort', 'name').strip().lower()
    direction = request.args.get('direction', 'asc').strip().lower()
    descending = direction == 'desc'
    sort_columns = {
        'name': [Tenant.name],
        'status': [Tenant.status, Tenant.name],
        'country': [Tenant.country, Tenant.name],
        'industry': [Tenant.industry, Tenant.name],
        'people': [user_count, Tenant.name],
        'admins': [admin_count, Tenant.name],
        'created_at': [Tenant.created_at],
    }
    columns = sort_columns.get(sort, sort_columns['name'])
    order = [
        column.desc() if descending else column.asc()
        for column in columns
    ]
    return query.order_by(*order, Tenant.id.asc())


def _primary_admins(tenant_ids):
    if not tenant_ids:
        return {}
    users = (
        User.query
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.tenant_id.in_(tenant_ids),
            User.deleted_at.is_(None),
            Role.name == 'CLIENT_ADMIN',
        )
        .order_by(User.created_at.asc())
        .all()
    )
    primary = {}
    for user in users:
        primary.setdefault(
            str(user.tenant_id),
            {
                'id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'is_active': user.is_active,
                'account_status': user.account_status,
                'invitation_sent_at': (
                    user.invitation_sent_at.isoformat()
                    if user.invitation_sent_at
                    else None
                ),
            },
        )
    return primary


@tenant_bp.get('')
@jwt_required()
@permission_required('tenant:read')
def list_tenants():
    page, per_page = get_pagination(default_per_page=12)
    user_count = _tenant_user_count_subquery()
    admin_count = _tenant_admin_count_subquery()
    query = _tenant_scope_query().with_entities(
        Tenant,
        user_count.label('user_count'),
        admin_count.label('admin_count'),
    )
    query = _apply_tenant_filters(query)
    query = _apply_tenant_sort(query, user_count, admin_count)
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    tenant_ids = [row[0].id for row in pagination.items]
    primary_admins = _primary_admins(tenant_ids)
    items = []
    for tenant, people, admins in pagination.items:
        item = tenant.to_dict()
        item.update({
            'user_count': int(people or 0),
            'admin_count': int(admins or 0),
            'primary_admin': primary_admins.get(str(tenant.id)),
        })
        items.append(item)
    return success({
        'items': items,
        'meta': {
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev,
        },
    })


@tenant_bp.get('/summary')
@jwt_required()
@permission_required('tenant:read')
def tenant_summary():
    tenants = _tenant_scope_query()
    users = User.query.filter(User.deleted_at.is_(None))
    if current_user.has_role('SUPER_ADMIN'):
        users = users.filter(User.tenant_id.is_not(None))
    else:
        users = users.filter(User.tenant_id == current_user.tenant_id)

    admin_count = (
        db.session.query(db.func.count(db.func.distinct(User.id)))
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(
            User.deleted_at.is_(None),
            Role.name == 'CLIENT_ADMIN',
        )
    )
    if current_user.has_role('SUPER_ADMIN'):
        admin_count = admin_count.filter(User.tenant_id.is_not(None))
    else:
        admin_count = admin_count.filter(
            User.tenant_id == current_user.tenant_id
        )

    return success({
        'total': tenants.count(),
        'active': tenants.filter(Tenant.status == 'active').count(),
        'suspended': tenants.filter(Tenant.status == 'suspended').count(),
        'archived': tenants.filter(Tenant.status == 'archived').count(),
        'users': users.count(),
        'admins': int(admin_count.scalar() or 0),
    })


@tenant_bp.get('/options')
@jwt_required()
@permission_required('tenant:read')
def tenant_options():
    tenants = _tenant_scope_query().order_by(Tenant.name.asc()).all()
    return success({
        'items': [
            {
                'id': str(tenant.id),
                'name': tenant.name,
                'status': tenant.status,
            }
            for tenant in tenants
        ]
    })


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
        return fail(
            'FORBIDDEN',
            'Only platform super administrators can provision '
            'organization administrators',
            403,
        )

    try:
        payload = OrganizationProvisionSchema().load(request.get_json() or {})
        tenant = Tenant(**payload['organization'])
        db.session.add(tenant)
        db.session.flush()

        admin_payload = {
            **payload['admin'],
            'tenant_id': tenant.id,
            'roles': ['CLIENT_ADMIN'],
        }
        admin = register_invited_user(
            admin_payload,
            actor=current_user,
            commit=False,
        )
        account_token, raw_token = issue_account_token(
            admin,
            AccountToken.PURPOSE_ACCOUNT_INVITE,
        )
        log_event(
            'tenant.create',
            'Tenant',
            tenant.id,
            tenant_id=tenant.id,
        )
        log_event(
            'tenant.admin_provisioned',
            'User',
            admin.id,
            tenant_id=tenant.id,
            metadata={
                'role': 'CLIENT_ADMIN',
                'activation_required': True,
            },
        )
        log_event(
            'user.invited',
            'AccountToken',
            account_token.id,
            tenant_id=tenant.id,
            actor=current_user,
            metadata={'user_id': str(admin.id)},
        )
        db.session.commit()
    except ValidationError as err:
        db.session.rollback()
        return fail('VALIDATION_ERROR', err.messages, 422)
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        message = (
            'Organization name, slug or administrator email is already in use'
            if isinstance(exc, IntegrityError)
            else str(exc)
        )
        return fail('ORGANIZATION_PROVISION_FAILED', message, 400)
    except Exception:
        db.session.rollback()
        raise

    delivery = 'sent'
    try:
        send_account_invitation_email(admin, raw_token)
        admin.invitation_sent_at = utcnow()
        log_event(
            'user.invitation_sent',
            'User',
            admin.id,
            tenant_id=tenant.id,
            actor=current_user,
            metadata={'account_token_id': str(account_token.id)},
        )
        db.session.commit()
    except EmailDeliveryError:
        db.session.rollback()
        delivery = 'failed'
        log_event(
            'user.invitation_delivery_failed',
            'User',
            admin.id,
            tenant_id=tenant.id,
            actor=current_user,
            metadata={
                'account_token_id': str(account_token.id),
                'trigger': 'organization_provisioning',
            },
        )
        db.session.commit()

    invitation = {
        'delivery': delivery,
        'expires_at': account_token.expires_at.isoformat(),
        'sent_at': (
            admin.invitation_sent_at.isoformat()
            if admin.invitation_sent_at
            else None
        ),
    }
    message = (
        'Organization provisioned and administrator invitation sent'
        if delivery == 'sent'
        else (
            'Organization provisioned, but the administrator invitation '
            'could not be delivered. Resend it from Access & users.'
        )
    )
    return success(
        {
            'organization': tenant.to_dict(),
            'admin': admin.to_dict(),
            'invitation': invitation,
        },
        message,
        201,
    )


@tenant_bp.get('/<tenant_id>')
@jwt_required()
@permission_required('tenant:read')
def get_tenant(tenant_id):
    return success(_accessible_tenant(tenant_id).to_dict())


@tenant_bp.patch('/<tenant_id>')
@jwt_required()
@permission_required('tenant:update')
def update_tenant(tenant_id):
    tenant = _accessible_tenant(tenant_id)
    try:
        payload = TenantUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    previous_status = tenant.status
    for key, value in payload.items():
        setattr(tenant, key, value)

    revoked_sessions = 0
    if previous_status == 'active' and tenant.status != 'active':
        tenant_users = User.query.filter(
            User.tenant_id == tenant.id,
            User.deleted_at.is_(None),
        ).all()
        for user in tenant_users:
            revoked_sessions += revoke_all_user_sessions(
                user,
                f'organization_{tenant.status}',
                commit=False,
            )

    log_event(
        'tenant.update',
        'Tenant',
        tenant.id,
        tenant_id=tenant.id,
        metadata={
            'previous_status': previous_status,
            'status': tenant.status,
            'revoked_sessions': revoked_sessions,
        },
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return fail(
            'TENANT_UPDATE_FAILED',
            'Organization name is already in use',
            409,
        )
    data = tenant.to_dict()
    data['revoked_sessions'] = revoked_sessions
    return success(data, 'Tenant updated')


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
