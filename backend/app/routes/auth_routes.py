from flask import Blueprint, request
from flask_jwt_extended import (
    current_user,
    get_jwt,
    jwt_required,
    set_access_cookies,
    set_refresh_cookies,
    unset_jwt_cookies,
)
from marshmallow import ValidationError

from app.extensions import db, limiter
from app.models import AuthSession
from app.schemas.auth_schema import LoginSchema, RegisterSchema
from app.services.auth_service import authenticate, register_user
from app.services.rbac_service import validate_role_assignment
from app.services.session_service import (
    RefreshTokenReuseError,
    SessionRevokedError,
    create_auth_session,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
    revoke_session_from_token,
    rotate_auth_session,
)
from app.utils.response import fail, success

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _request_ip():
    return request.remote_addr


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
        user = authenticate(payload['email'], payload['password'])
        _, access_token, refresh_token = create_auth_session(
            user,
            ip_address=_request_ip(),
            user_agent=request.headers.get('User-Agent'),
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except ValueError as exc:
        db.session.rollback()
        return fail('INVALID_CREDENTIALS', str(exc), 401)

    response, status = success({'user': user.to_dict()}, 'Login successful')
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response, status


@auth_bp.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    try:
        _, access_token, refresh_token = rotate_auth_session(current_user, get_jwt())
    except RefreshTokenReuseError as exc:
        response, status = fail('REFRESH_TOKEN_REUSED', str(exc), 401)
        unset_jwt_cookies(response)
        return response, status
    except SessionRevokedError as exc:
        response, status = fail('SESSION_REVOKED', str(exc), 401)
        unset_jwt_cookies(response)
        return response, status

    response, status = success({}, 'Authentication session rotated')
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response, status


@auth_bp.get('/me')
@jwt_required()
def me():
    return success(current_user.to_dict())


@auth_bp.get('/sessions')
@jwt_required()
def sessions():
    current_session_id = get_jwt().get('sid')
    data = [session.to_dict(current_session_id) for session in list_user_sessions(current_user)]
    return success(data)


@auth_bp.delete('/sessions/<uuid:session_id>')
@jwt_required()
def revoke_user_session(session_id):
    auth_session = db.session.get(AuthSession, session_id)
    if not auth_session or auth_session.user_id != current_user.id:
        return fail('SESSION_NOT_FOUND', 'Authentication session was not found', 404)

    revoke_session(auth_session, 'user_forced_logout')
    db.session.commit()

    response, status = success({}, 'Authentication session revoked')
    if str(auth_session.id) == str(get_jwt().get('sid')):
        unset_jwt_cookies(response)
    return response, status


@auth_bp.post('/logout-all')
@jwt_required()
def logout_all():
    revoked_count = revoke_all_user_sessions(current_user, 'user_logout_all', get_jwt())
    response, status = success({'revoked_sessions': revoked_count}, 'All authentication sessions revoked')
    unset_jwt_cookies(response)
    return response, status


@auth_bp.post('/logout')
@jwt_required()
def logout():
    revoke_session_from_token(get_jwt(), 'user_logout')
    response, status = success({}, 'Logged out')
    unset_jwt_cookies(response)
    return response, status
