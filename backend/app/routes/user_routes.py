from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import AccountToken, Employee, Role, Tenant, User, UserRole
from app.models.base import utcnow
from app.schemas.user_schema import (
    MfaAdminResetSchema,
    UserCreateSchema,
    UserEmployeeLinkSchema,
    UserRoleUpdateSchema,
    UserUpdateSchema,
)
from app.services.account_recovery_service import (
    issue_account_token,
    send_account_invitation_email,
)
from app.services.auth_service import register_invited_user
from app.services.audit_service import log_event
from app.services.employee_service import create_employee
from app.services.mfa_policy_service import (
    administrative_reset_mfa,
)
from app.services.mfa_service import (
    MfaError,
    password_is_valid,
    verify_current_totp,
)
from app.services.rbac_service import set_user_roles, validate_role_assignment
from app.services.session_service import revoke_all_user_sessions
from app.utils.decorators import permission_required, tenant_query
from app.utils.email import EmailDeliveryError
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

user_bp = Blueprint('users', __name__, url_prefix='/users')

PRIVILEGED_ROLES = {
    'SUPER_ADMIN',
    'CLIENT_ADMIN',
    'ORGANIZATION_OWNER',
    'HR_CONSULTANT',
}


def _user_scope_query():
    return tenant_query(User).filter(User.deleted_at.is_(None))


def _has_role(role_names):
    return User.role_links.any(
        UserRole.role.has(Role.name.in_(role_names))
    )


def _can_manage_user(user):
    if current_user.has_role('SUPER_ADMIN'):
        return True
    return not user.has_any_role(PRIVILEGED_ROLES)


def _invitation_data(user, account_token, delivery):
    return {
        'delivery': delivery,
        'expires_at': (
            account_token.expires_at.isoformat()
            if account_token
            else None
        ),
        'sent_at': (
            user.invitation_sent_at.isoformat()
            if user.invitation_sent_at
            else None
        ),
    }


def _apply_user_filters(query):
    search = request.args.get('q', '').strip().lower()
    if search:
        like = f'%{search}%'
        query = query.filter(
            or_(
                db.func.lower(User.first_name).like(like),
                db.func.lower(User.last_name).like(like),
                db.func.lower(User.email).like(like),
                db.func.lower(
                    User.first_name + ' ' + User.last_name
                ).like(like),
                db.func.lower(Tenant.name).like(like),
                User.role_links.any(
                    UserRole.role.has(
                        db.func.lower(Role.name).like(like)
                    )
                ),
            )
        )

    status = request.args.get('status', '').strip().lower()
    if status == 'active':
        query = query.filter(
            User.is_active.is_(True),
            User.activation_required.is_(False),
        )
    elif status == 'invited':
        query = query.filter(
            User.is_active.is_(True),
            User.activation_required.is_(True),
        )
    elif status == 'inactive':
        query = query.filter(User.is_active.is_(False))

    role = request.args.get('role', '').strip().upper()
    if role:
        query = query.filter(_has_role({role}))

    verified = request.args.get('verified', '').strip().lower()
    if verified == 'true':
        query = query.filter(User.email_verified_at.is_not(None))
    elif verified == 'false':
        query = query.filter(User.email_verified_at.is_(None))

    mfa = request.args.get('mfa', '').strip().lower()
    if mfa == 'enabled':
        query = query.filter(User.mfa_enabled_at.is_not(None))
    elif mfa == 'disabled':
        query = query.filter(User.mfa_enabled_at.is_(None))

    return query


def _apply_user_sort(query):
    sort = request.args.get('sort', 'full_name').strip().lower()
    direction = request.args.get('direction', 'asc').strip().lower()
    descending = direction == 'desc'

    sort_columns = {
        'full_name': [User.first_name, User.last_name],
        'email': [User.email],
        'organization': [Tenant.name, User.first_name, User.last_name],
        'status': [
            User.is_active,
            User.activation_required,
            User.first_name,
            User.last_name,
        ],
        'verified': [User.email_verified_at, User.first_name, User.last_name],
        'mfa': [User.mfa_enabled_at, User.first_name, User.last_name],
        'last_login': [User.last_login_at, User.first_name, User.last_name],
        'created_at': [User.created_at],
    }
    columns = sort_columns.get(sort, sort_columns['full_name'])
    order = [
        column.desc() if descending else column.asc()
        for column in columns
    ]
    return query.order_by(*order, User.id.asc())


@user_bp.get('')
@jwt_required()
@permission_required('user:read')
def list_users():
    page, per_page = get_pagination(default_per_page=15)
    query = _user_scope_query().outerjoin(
        Tenant,
        User.tenant_id == Tenant.id,
    )
    query = _apply_user_filters(query)
    query = _apply_user_sort(query)
    pagination = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return success(paginated_response(pagination))


@user_bp.get('/summary')
@jwt_required()
@permission_required('user:read')
def user_summary():
    query = _user_scope_query()
    return success({
        'total': query.count(),
        'active': query.filter(
            User.is_active.is_(True),
            User.activation_required.is_(False),
        ).count(),
        'invited': query.filter(
            User.is_active.is_(True),
            User.activation_required.is_(True),
        ).count(),
        'verified': query.filter(
            User.email_verified_at.is_not(None)
        ).count(),
        'mfa_enabled': query.filter(
            User.mfa_enabled_at.is_not(None)
        ).count(),
        'privileged': query.filter(
            _has_role(PRIVILEGED_ROLES)
        ).count(),
    })


@user_bp.post('')
@jwt_required()
@permission_required('user:create')
def create_user():
    try:
        payload = UserCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    employee_payload = payload.pop('employee_profile', None)
    if not current_user.has_role('SUPER_ADMIN'):
        payload['tenant_id'] = current_user.tenant_id

    try:
        validate_role_assignment(
            current_user,
            payload['roles'],
            payload.get('tenant_id'),
        )
        user = register_invited_user(
            payload,
            actor=current_user,
            commit=False,
        )
        employee = None

        if employee_payload:
            if not user.tenant_id:
                raise ValueError(
                    'An organization is required when creating an employee profile'
                )
            employee_payload = {
                **employee_payload,
                'user_id': user.id,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
            }
            employee = create_employee(
                employee_payload,
                user.tenant_id,
                commit=False,
            )

        account_token, raw_token = issue_account_token(
            user,
            AccountToken.PURPOSE_ACCOUNT_INVITE,
        )
        log_event(
            'user.invited',
            'AccountToken',
            account_token.id,
            tenant_id=user.tenant_id,
            actor=current_user,
            metadata={'user_id': str(user.id)},
        )
        log_event(
            'user.create',
            'User',
            user.id,
            tenant_id=user.tenant_id,
        )
        db.session.commit()
    except (ValueError, IntegrityError) as exc:
        db.session.rollback()
        message = (
            'User or employee identifier is already in use'
            if isinstance(exc, IntegrityError)
            else str(exc)
        )
        return fail('USER_CREATE_FAILED', message, 400)
    except Exception:
        db.session.rollback()
        raise

    delivery = 'sent'
    try:
        send_account_invitation_email(user, raw_token)
        user.invitation_sent_at = utcnow()
        log_event(
            'user.invitation_sent',
            'User',
            user.id,
            tenant_id=user.tenant_id,
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
            user.id,
            tenant_id=user.tenant_id,
            actor=current_user,
            metadata={'account_token_id': str(account_token.id)},
        )
        db.session.commit()

    data = user.to_dict()
    if employee:
        data['employee_profile'] = employee.to_dict()
    data['invitation'] = _invitation_data(
        user,
        account_token,
        delivery,
    )
    message = (
        'User created and invitation sent'
        if delivery == 'sent'
        else (
            'User created, but the invitation email could not be delivered. '
            'Resend the invitation from Access & users.'
        )
    )
    return success(data, message, 201)


@user_bp.get('/options')
@jwt_required()
@permission_required('user:read')
def user_options():
    query = _user_scope_query().filter(
        User.is_active.is_(True),
        User.activation_required.is_(False),
    ).order_by(
        User.first_name.asc(),
        User.last_name.asc(),
    )
    return success({'items': [user.to_dict() for user in query.all()]})


@user_bp.post('/<user_id>/invitation/resend')
@jwt_required()
@permission_required('user:update')
def resend_user_invitation(user_id):
    user = _user_scope_query().filter_by(id=user_id).first_or_404()
    if not _can_manage_user(user):
        return fail(
            'PRIVILEGED_USER_PROTECTED',
            'Only a platform administrator can manage this account',
            403,
        )
    if not user.is_active or not user.activation_required:
        return fail(
            'INVITATION_NOT_AVAILABLE',
            'Only active accounts awaiting activation can be reinvited',
            409,
        )

    account_token, raw_token = issue_account_token(
        user,
        AccountToken.PURPOSE_ACCOUNT_INVITE,
    )
    log_event(
        'user.invitation_resent',
        'AccountToken',
        account_token.id,
        tenant_id=user.tenant_id,
        actor=current_user,
        metadata={'user_id': str(user.id)},
    )
    db.session.commit()

    try:
        send_account_invitation_email(user, raw_token)
    except EmailDeliveryError:
        log_event(
            'user.invitation_delivery_failed',
            'User',
            user.id,
            tenant_id=user.tenant_id,
            actor=current_user,
            metadata={
                'account_token_id': str(account_token.id),
                'trigger': 'resend',
            },
        )
        db.session.commit()
        return fail(
            'EMAIL_DELIVERY_FAILED',
            'The invitation could not be delivered. Try again later.',
            503,
        )

    user.invitation_sent_at = utcnow()
    log_event(
        'user.invitation_sent',
        'User',
        user.id,
        tenant_id=user.tenant_id,
        actor=current_user,
        metadata={
            'account_token_id': str(account_token.id),
            'trigger': 'resend',
        },
    )
    db.session.commit()
    return success(
        {
            'user': user.to_dict(),
            'invitation': _invitation_data(
                user,
                account_token,
                'sent',
            ),
        },
        'Invitation sent',
    )


@user_bp.get('/<user_id>')
@jwt_required()
@permission_required('user:read')
def get_user(user_id):
    user = _user_scope_query().filter_by(id=user_id).first_or_404()
    return success(user.to_dict())


@user_bp.patch('/<user_id>')
@jwt_required()
@permission_required('user:update')
def update_user(user_id):
    user = _user_scope_query().filter_by(id=user_id).first_or_404()
    try:
        payload = UserUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    if (
        str(user.id) == str(current_user.id)
        and payload.get('is_active') is False
    ):
        return fail(
            'SELF_DEACTIVATION_NOT_ALLOWED',
            'You cannot deactivate your own account',
            409,
        )
    if not _can_manage_user(user):
        return fail(
            'PRIVILEGED_USER_PROTECTED',
            'Only a platform administrator can update this account',
            403,
        )

    previous_active = user.is_active
    for key, value in payload.items():
        setattr(user, key, value)

    revoked_sessions = 0
    if previous_active and not user.is_active:
        revoked_sessions = revoke_all_user_sessions(
            user,
            'account_deactivated_by_administrator',
            commit=False,
        )

    log_event(
        'user.update',
        'User',
        user.id,
        tenant_id=user.tenant_id,
        metadata={
            'is_active': user.is_active,
            'revoked_sessions': revoked_sessions,
        },
    )
    db.session.commit()
    data = user.to_dict()
    data['revoked_sessions'] = revoked_sessions
    return success(data, 'User updated')


@user_bp.patch('/<user_id>/roles')
@jwt_required()
@permission_required('user:update')
def update_roles(user_id):
    user = _user_scope_query().filter_by(id=user_id).first_or_404()
    if not _can_manage_user(user):
        return fail(
            'PRIVILEGED_USER_PROTECTED',
            'Only a platform administrator can update this account',
            403,
        )
    try:
        payload = UserRoleUpdateSchema().load(request.get_json() or {})
        requested_roles = payload['roles']
        if (
            str(user.id) == str(current_user.id)
            and user.has_role('SUPER_ADMIN')
            and 'SUPER_ADMIN' not in requested_roles
        ):
            raise ValueError(
                'You cannot remove your own platform administrator role'
            )
        validate_role_assignment(
            current_user,
            requested_roles,
            user.tenant_id,
        )
        set_user_roles(
            user,
            requested_roles,
            assigned_by_id=current_user.id,
            commit=False,
        )
        log_event(
            'user.roles_update',
            'User',
            user.id,
            tenant_id=user.tenant_id,
            metadata={'roles': requested_roles},
        )
        db.session.commit()
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail('ROLE_UPDATE_FAILED', getattr(err, 'messages', str(err)), 400)
    return success(user.to_dict(), 'User roles updated')


@user_bp.post('/<user_id>/mfa/reset')
@jwt_required()
@permission_required('security:mfa_reset')
def reset_user_mfa(user_id):
    target = User.query.filter_by(
        id=user_id,
        deleted_at=None,
    ).first_or_404()
    if (
        not current_user.has_role('SUPER_ADMIN')
        and str(current_user.tenant_id) != str(target.tenant_id)
    ):
        return fail(
            'FORBIDDEN',
            'MFA can only be reset within your organization',
            403,
        )

    try:
        payload = MfaAdminResetSchema().load(
            request.get_json(silent=True) or {}
        )
        if not password_is_valid(
            current_user,
            payload['password'],
        ):
            raise MfaError('invalid_password')
        verify_current_totp(
            current_user,
            payload['code'],
        )
        result = administrative_reset_mfa(
            target,
            current_user,
            payload['reason'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except PermissionError as exc:
        return fail('FORBIDDEN', str(exc), 403)
    except MfaError:
        db.session.rollback()
        return fail(
            'MFA_STEP_UP_REQUIRED',
            'A valid administrator password and authenticator code are required',
            401,
        )
    except ValueError as exc:
        return fail('MFA_RESET_FAILED', str(exc), 409)

    log_event(
        'security.mfa_reset',
        'User',
        target.id,
        tenant_id=target.tenant_id,
        actor=current_user,
        metadata={
            'reason': payload['reason'],
            'revoked_sessions': result['revoked_sessions'],
        },
    )
    db.session.commit()
    return success(result, 'User MFA enrollment reset')


@user_bp.patch('/<user_id>/employee-link')
@jwt_required()
@permission_required('user:update')
def link_user_employee(user_id):
    user = _user_scope_query().filter_by(id=user_id).first_or_404()
    if not _can_manage_user(user) and not current_user.has_role('SUPER_ADMIN'):
        return fail(
            'PRIVILEGED_USER_PROTECTED',
            'Only a platform administrator can update this account',
            403,
        )

    try:
        payload = UserEmployeeLinkSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    employee_id = payload.get('employee_id')
    previous = user.employee_profile
    if employee_id is None:
        if previous:
            previous.user_id = None
            log_event(
                'employee.access_unlinked',
                'Employee',
                previous.id,
                tenant_id=previous.tenant_id,
                metadata={'user_id': str(user.id)},
            )
        db.session.commit()
        return success(user.to_dict(), 'Employee link removed')

    if not user.tenant_id:
        return fail(
            'TENANT_REQUIRED',
            'Platform accounts cannot be linked to employee records',
            422,
        )

    employee = tenant_query(Employee).filter(
        Employee.id == employee_id,
        Employee.deleted_at.is_(None),
    ).first()
    if not employee or str(employee.tenant_id) != str(user.tenant_id):
        return fail(
            'EMPLOYEE_NOT_FOUND',
            'Employee was not found in this organization',
            404,
        )
    if employee.user_id and str(employee.user_id) != str(user.id):
        return fail(
            'EMPLOYEE_ALREADY_LINKED',
            'This employee is already linked to another account',
            409,
        )

    if previous and str(previous.id) != str(employee.id):
        previous.user_id = None
    employee.user_id = user.id
    log_event(
        'employee.access_linked',
        'Employee',
        employee.id,
        tenant_id=employee.tenant_id,
        metadata={'user_id': str(user.id)},
    )
    db.session.commit()
    return success(user.to_dict(), 'Employee account linked')
