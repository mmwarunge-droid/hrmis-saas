from flask import Blueprint, request
from flask_jwt_extended import current_user, jwt_required
from marshmallow import ValidationError

from app.extensions import db
from app.models import User
from app.schemas.user_schema import UserCreateSchema, UserRoleUpdateSchema, UserUpdateSchema
from app.services.auth_service import register_user
from app.services.audit_service import log_event
from app.services.rbac_service import set_user_roles, validate_role_assignment
from app.utils.decorators import permission_required, tenant_query
from app.utils.pagination import get_pagination, paginated_response
from app.utils.response import fail, success

user_bp = Blueprint('users', __name__, url_prefix='/users')


@user_bp.get('')
@jwt_required()
@permission_required('user:read')
def list_users():
    page, per_page = get_pagination()
    query = tenant_query(User).filter(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    return success(paginated_response(query.paginate(page=page, per_page=per_page, error_out=False)))


@user_bp.post('')
@jwt_required()
@permission_required('user:create')
def create_user():
    try:
        payload = UserCreateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    if not current_user.has_role('SUPER_ADMIN'):
        payload['tenant_id'] = current_user.tenant_id
    try:
        validate_role_assignment(current_user, payload['roles'], payload.get('tenant_id'))
        user = register_user(payload, actor=current_user)
        log_event('user.create', 'User', user.id, tenant_id=user.tenant_id)
    except ValueError as exc:
        db.session.rollback()
        return fail('USER_CREATE_FAILED', str(exc), 400)
    return success(user.to_dict(), 'User created', 201)


@user_bp.get('/<user_id>')
@jwt_required()
@permission_required('user:read')
def get_user(user_id):
    return success(tenant_query(User).filter_by(id=user_id, deleted_at=None).first_or_404().to_dict())


@user_bp.patch('/<user_id>')
@jwt_required()
@permission_required('user:update')
def update_user(user_id):
    user = tenant_query(User).filter_by(id=user_id, deleted_at=None).first_or_404()
    try:
        payload = UserUpdateSchema().load(request.get_json() or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    for key, value in payload.items():
        setattr(user, key, value)
    log_event('user.update', 'User', user.id, tenant_id=user.tenant_id)
    db.session.commit()
    return success(user.to_dict(), 'User updated')


@user_bp.patch('/<user_id>/roles')
@jwt_required()
@permission_required('user:update')
def update_roles(user_id):
    user = tenant_query(User).filter_by(id=user_id, deleted_at=None).first_or_404()
    try:
        payload = UserRoleUpdateSchema().load(request.get_json() or {})
        validate_role_assignment(current_user, payload['roles'], user.tenant_id)
        set_user_roles(user, payload['roles'], assigned_by_id=current_user.id, commit=True)
        log_event('user.roles_update', 'User', user.id, tenant_id=user.tenant_id, metadata={'roles': payload['roles']})
    except (ValidationError, ValueError) as err:
        db.session.rollback()
        return fail('ROLE_UPDATE_FAILED', getattr(err, 'messages', str(err)), 400)
    return success(user.to_dict(), 'User roles updated')
