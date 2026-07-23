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
from app.services.audit_service import identifier_fingerprint, log_event
from app.services.auth_service import AuthenticationError, authenticate, register_user
from app.services.rbac_service import validate_role_assignment
from app.services.session_service import (
    RefreshTokenReuseError,
    SessionRevokedError,
    create_auth_session,
    detect_login_risk,
    list_user_sessions,
    revoke_all_user_sessions,
    revoke_session,
    revoke_session_from_token,
    rotate_auth_session,
)
from app.utils.request_security import request_ip_address
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
    raw_payload = request.get_json(silent=True) or {}
    try:
        payload = LoginSchema().load(raw_payload)
    except ValidationError as err:
        log_event(
            'auth.login_rejected',
            'Authentication',
            actor=None,
            metadata={
                'reason': 'validation_error',
                'identifier_fingerprint': identifier_fingerprint(raw_payload.get('email')),
            },
        )
        db.session.commit()
        return fail('VALIDATION_ERROR', err.messages, 422)

    try:
        user = authenticate(payload['email'], payload['password'])
    except AuthenticationError as exc:
        target = exc.user
        metadata = {
            'reason': exc.reason,
            'identifier_fingerprint': identifier_fingerprint(payload['email']),
            'failed_attempts': getattr(target, 'failed_login_attempts', None),
        }
        log_event(
            'auth.login_failed',
            'User',
            entity_id=getattr(target, 'id', None),
            tenant_id=getattr(target, 'tenant_id', None),
            actor=None,
            metadata=metadata,
        )
        if exc.newly_locked:
            log_event(
                'auth.account_locked',
                'User',
                entity_id=target.id,
                tenant_id=target.tenant_id,
                actor=None,
                metadata={
                    'failed_attempts': target.failed_login_attempts,
                    'locked_until': target.locked_until.isoformat(),
                },
            )
        db.session.commit()
        return fail('INVALID_CREDENTIALS', AuthenticationError.public_message, 401)

    ip_address = request_ip_address()
    user_agent = request.headers.get('User-Agent')
    risk_flags = detect_login_risk(user, ip_address=ip_address, user_agent=user_agent)
    auth_session, access_token, refresh_token = create_auth_session(
        user,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    log_event(
        'auth.login_succeeded',
        'AuthSession',
        entity_id=auth_session.id,
        tenant_id=user.tenant_id,
        actor=user,
        metadata={'risk_flags': risk_flags},
    )
    if risk_flags:
        log_event(
            'auth.suspicious_login',
            'AuthSession',
            entity_id=auth_session.id,
            tenant_id=user.tenant_id,
            actor=user,
            metadata={'risk_flags': risk_flags},
        )
    db.session.commit()

    response, status = success({'user': user.to_dict()}, 'Login successful')
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response, status


@auth_bp.post('/refresh')
@jwt_required(refresh=True)
def refresh():
    jwt_data = get_jwt()
    try:
        _, access_token, refresh_token = rotate_auth_session(current_user, jwt_data)
    except RefreshTokenReuseError as exc:
        log_event(
            'auth.refresh_token_reuse',
            'AuthSession',
            entity_id=jwt_data.get('sid'),
            actor=current_user,
            metadata={'session_revoked': True},
        )
        db.session.commit()
        response, status = fail('REFRESH_TOKEN_REUSED', str(exc), 401)
        unset_jwt_cookies(response)
        return response, status
    except SessionRevokedError as exc:
        log_event(
            'auth.refresh_rejected',
            'AuthSession',
            entity_id=jwt_data.get('sid'),
            actor=current_user,
            metadata={'reason': 'session_revoked'},
        )
        db.session.commit()
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

    current_session = str(auth_session.id) == str(get_jwt().get('sid'))
    revoke_session(auth_session, 'user_forced_logout')
    log_event(
        'auth.session_revoked',
        'AuthSession',
        entity_id=auth_session.id,
        actor=current_user,
        metadata={'reason': 'user_forced_logout', 'current_session': current_session},
    )
    db.session.commit()

    response, status = success({}, 'Authentication session revoked')
    if current_session:
        unset_jwt_cookies(response)
    return response, status


@auth_bp.post('/logout-all')
@jwt_required()
def logout_all():
    jwt_data = get_jwt()
    revoked_count = revoke_all_user_sessions(current_user, 'user_logout_all', jwt_data)
    log_event(
        'auth.logout_all',
        'User',
        entity_id=current_user.id,
        actor=current_user,
        metadata={'revoked_sessions': revoked_count, 'session_id': jwt_data.get('sid')},
    )
    db.session.commit()
    response, status = success({'revoked_sessions': revoked_count}, 'All authentication sessions revoked')
    unset_jwt_cookies(response)
    return response, status


@auth_bp.post('/logout')
@jwt_required()
def logout():
    jwt_data = get_jwt()
    revoke_session_from_token(jwt_data, 'user_logout')
    log_event(
        'auth.logout',
        'AuthSession',
        entity_id=jwt_data.get('sid'),
        actor=current_user,
        metadata={'reason': 'user_logout'},
    )
    db.session.commit()
    response, status = success({}, 'Logged out')
    unset_jwt_cookies(response)
    return response, status
