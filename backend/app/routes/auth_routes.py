from flask import Blueprint, request
from flask_jwt_extended import current_user, create_access_token, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from app.extensions import db, limiter
from app.models import User
from app.schemas.auth_schema import LoginSchema, RegisterSchema
from app.services.auth_service import authenticate, claims_for, register_user
from app.services.rbac_service import validate_role_assignment
from app.utils.response import fail, success

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.post('/register')
@jwt_required()
def register():
    """Create a user through an authenticated administrative workflow.

    The initial SUPER_ADMIN must be provisioned with the ``bootstrap-admin``
    Flask CLI command; public first-user bootstrap is intentionally disabled.
    """
    if not current_user.has_permissions({'user:create'}):
        return fail('FORBIDDEN', 'Insufficient permissions to register users', 403)

    try:
        payload = RegisterSchema().load(request.get_json() or {})
        if not current_user.has_role('SUPER_ADMIN'):
            payload['tenant_id'] = current_user.tenant_id
        validate_role_assignment(current_user, payload.get('roles') or ['EMPLOYEE'], payload.get('tenant_id'))
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        return fail('FORBIDDEN_ROLE_ASSIGNMENT', str(exc), 403)

    try:
        user = register_user(payload, actor=current_user)
    except ValueError as exc:
        db.session.rollback()
        return fail('REGISTRATION_FAILED', str(exc), 400)
    return success(user.to_dict(), 'User registered', 201)


@auth_bp.post('/login')
@limiter.limit('10 per minute')
def login():
    try:
        payload = LoginSchema().load(request.get_json() or {})
        user, access_token, refresh_token = authenticate(payload['email'], payload['password'])
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        return fail('INVALID_CREDENTIALS', str(exc), 401)
    return success({'access_token': access_token, 'refresh_token': refresh_token, 'user': user.to_dict()}, 'Login successful')


@auth_bp.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, get_jwt_identity())
    if not user or not user.is_active or user.deleted_at is not None:
        return fail('INVALID_TOKEN', 'User no longer exists or is inactive', 401)
    return success({'access_token': create_access_token(identity=str(user.id), additional_claims=claims_for(user))})


@auth_bp.get('/me')
@jwt_required()
def me():
    return success(current_user.to_dict())


@auth_bp.post('/logout')
@jwt_required()
def logout():
    # Token revocation is introduced in the authentication-hardening phase.
    return success({}, 'Logged out')
