from flask import Blueprint, current_app, request
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
from app.models import AuthSession, User
from app.schemas.auth_schema import (
    ForgotPasswordSchema,
    LoginSchema,
    MfaChallengeSchema,
    MfaEnrollmentStartSchema,
    MfaRecoveryCodesSchema,
    RegisterSchema,
    ResetPasswordSchema,
    VerifyEmailSchema,
)
from app.services.account_recovery_service import (
    AccountTokenError,
    PasswordReuseError,
    issue_account_token,
    reset_password_with_token,
    send_email_verification_email,
    send_password_reset_email,
    token_fingerprint,
    verify_email_with_token,
)
from app.services.audit_service import identifier_fingerprint, log_event
from app.services.auth_service import (
    AuthenticationError,
    authenticate,
    record_successful_login,
    register_user,
)
from app.services.mfa_service import (
    MfaError,
    confirm_mfa_enrollment,
    generate_recovery_codes,
    is_mfa_required,
    issue_mfa_challenge,
    mfa_status,
    start_mfa_enrollment,
    verify_current_totp,
    verify_mfa_challenge,
)
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
from app.utils.email import EmailDeliveryError
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


@auth_bp.post('/password/forgot')
@limiter.limit('5 per hour;2 per minute')
def forgot_password():
    raw_payload = request.get_json(silent=True) or {}
    try:
        payload = ForgotPasswordSchema().load(raw_payload)
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    normalized_email = payload['email'].strip().lower()
    fingerprint = identifier_fingerprint(normalized_email)
    user = User.query.filter(
        User.email == normalized_email,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).first()

    if not user:
        log_event(
            'auth.password_reset_requested',
            'Authentication',
            actor=None,
            metadata={'identifier_fingerprint': fingerprint},
        )
        db.session.commit()
        return success({}, 'If the account exists, password reset instructions will be sent', 202)

    user_id = user.id
    tenant_id = user.tenant_id
    try:
        account_token, raw_token = issue_account_token(user, 'password_reset')
        send_password_reset_email(user, raw_token)
        log_event(
            'auth.password_reset_requested',
            'AccountToken',
            entity_id=account_token.id,
            tenant_id=tenant_id,
            actor=None,
            metadata={'identifier_fingerprint': fingerprint},
        )
        db.session.commit()
    except EmailDeliveryError:
        db.session.rollback()
        log_event(
            'auth.password_reset_delivery_failed',
            'User',
            entity_id=user_id,
            tenant_id=tenant_id,
            actor=None,
            metadata={'identifier_fingerprint': fingerprint},
        )
        db.session.commit()

    return success({}, 'If the account exists, password reset instructions will be sent', 202)


@auth_bp.post('/password/reset')
@limiter.limit('10 per hour')
def reset_password():
    try:
        payload = ResetPasswordSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    try:
        user, revoked_count = reset_password_with_token(payload['token'], payload['password'])
    except PasswordReuseError as exc:
        db.session.rollback()
        return fail('PASSWORD_REUSE_NOT_ALLOWED', str(exc), 422)
    except AccountTokenError:
        db.session.rollback()
        log_event(
            'auth.password_reset_rejected',
            'AccountToken',
            actor=None,
            metadata={'token_fingerprint': token_fingerprint(payload.get('token'))},
        )
        db.session.commit()
        return fail('INVALID_OR_EXPIRED_TOKEN', AccountTokenError.public_message, 400)

    log_event(
        'auth.password_reset_completed',
        'User',
        entity_id=user.id,
        tenant_id=user.tenant_id,
        actor=None,
        metadata={'revoked_sessions': revoked_count},
    )
    db.session.commit()

    response, status = success({}, 'Password reset completed')
    unset_jwt_cookies(response)
    return response, status


@auth_bp.post('/email-verification/request')
@jwt_required()
@limiter.limit('3 per hour')
def request_email_verification():
    if current_user.email_verified_at is not None:
        return success({}, 'Email address is already verified')

    try:
        account_token, raw_token = issue_account_token(current_user, 'email_verification')
        send_email_verification_email(current_user, raw_token)
        log_event(
            'auth.email_verification_requested',
            'AccountToken',
            entity_id=account_token.id,
            actor=current_user,
        )
        db.session.commit()
    except EmailDeliveryError:
        db.session.rollback()
        log_event(
            'auth.email_verification_delivery_failed',
            'User',
            entity_id=current_user.id,
            actor=current_user,
        )
        db.session.commit()
        return fail('EMAIL_DELIVERY_FAILED', 'Verification email could not be delivered', 503)

    return success({}, 'Verification instructions sent', 202)


@auth_bp.post('/email-verification/confirm')
@limiter.limit('10 per hour')
def confirm_email_verification():
    try:
        payload = VerifyEmailSchema().load(request.get_json(silent=True) or {})
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)

    try:
        user = verify_email_with_token(payload['token'])
    except AccountTokenError:
        db.session.rollback()
        log_event(
            'auth.email_verification_rejected',
            'AccountToken',
            actor=None,
            metadata={'token_fingerprint': token_fingerprint(payload.get('token'))},
        )
        db.session.commit()
        return fail('INVALID_OR_EXPIRED_TOKEN', AccountTokenError.public_message, 400)

    log_event(
        'auth.email_verified',
        'User',
        entity_id=user.id,
        tenant_id=user.tenant_id,
        actor=None,
    )
    db.session.commit()
    return success({'email_verified': True}, 'Email address verified')


def _mfa_error_response(exc: MfaError):
    status = 429 if exc.attempts_remaining == 0 else 401
    return fail('MFA_VERIFICATION_FAILED', MfaError.public_message, status)


def _complete_login(user, ip_address, user_agent, *, mfa_verified: bool, extra_data=None):
    risk_flags = detect_login_risk(user, ip_address=ip_address, user_agent=user_agent)
    auth_session, access_token, refresh_token = create_auth_session(
        user,
        ip_address=ip_address,
        user_agent=user_agent,
        mfa_verified=mfa_verified,
    )
    record_successful_login(user)
    log_event(
        'auth.login_succeeded',
        'AuthSession',
        entity_id=auth_session.id,
        tenant_id=user.tenant_id,
        actor=user,
        metadata={'risk_flags': risk_flags, 'mfa_verified': mfa_verified},
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

    data = {'user': user.to_dict()}
    data.update(extra_data or {})
    response, status = success(data, 'Login successful')
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    return response, status


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
    mfa_enrollment_required = is_mfa_required(user) and user.mfa_enabled_at is None
    mfa_verification_required = user.mfa_enabled_at is not None

    if mfa_enrollment_required or mfa_verification_required:
        if mfa_enrollment_required and user.email_verified_at is None:
            try:
                account_token, raw_token = issue_account_token(user, 'email_verification')
                send_email_verification_email(user, raw_token)
                log_event(
                    'auth.email_verification_requested',
                    'AccountToken',
                    entity_id=account_token.id,
                    actor=user,
                    metadata={'trigger': 'mfa_enrollment'},
                )
                db.session.commit()
            except EmailDeliveryError:
                db.session.rollback()
                log_event(
                    'auth.email_verification_delivery_failed',
                    'User',
                    entity_id=user.id,
                    actor=user,
                    metadata={'trigger': 'mfa_enrollment'},
                )
                db.session.commit()
            log_event(
                'auth.mfa_enrollment_blocked',
                'User',
                entity_id=user.id,
                actor=user,
                metadata={'reason': 'email_not_verified'},
            )
            db.session.commit()
            return fail(
                'EMAIL_VERIFICATION_REQUIRED',
                'Verify your email address before enrolling in multi-factor authentication',
                403,
            )

        purpose = 'enroll' if mfa_enrollment_required else 'verify'
        challenge_token = issue_mfa_challenge(
            user,
            purpose,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        log_event(
            'auth.mfa_challenge_issued',
            'User',
            entity_id=user.id,
            actor=user,
            metadata={'purpose': purpose},
        )
        db.session.commit()
        return success(
            {
                'mfa_required': True,
                'mfa_enrollment_required': mfa_enrollment_required,
                'challenge_token': challenge_token,
                'challenge_expires_seconds': current_app.config['MFA_CHALLENGE_MINUTES'] * 60,
            },
            'Multi-factor authentication required',
            202,
        )

    return _complete_login(user, ip_address, user_agent, mfa_verified=False)


@auth_bp.post('/mfa/enrollment/start')
@limiter.limit('10 per hour')
def mfa_enrollment_start():
    try:
        payload = MfaEnrollmentStartSchema().load(request.get_json(silent=True) or {})
        user, enrollment = start_mfa_enrollment(payload['challenge_token'])
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except MfaError as exc:
        return _mfa_error_response(exc)

    log_event('auth.mfa_enrollment_started', 'User', entity_id=user.id, actor=user)
    db.session.commit()
    return success(enrollment, 'Authenticator enrollment started')


@auth_bp.post('/mfa/enrollment/confirm')
@limiter.limit('10 per hour')
def mfa_enrollment_confirm():
    try:
        payload = MfaChallengeSchema().load(request.get_json(silent=True) or {})
        user, recovery_codes, challenge = confirm_mfa_enrollment(
            payload['challenge_token'],
            payload['code'],
        )
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except MfaError as exc:
        log_event('auth.mfa_enrollment_failed', 'Authentication', actor=None, metadata={'reason': exc.reason})
        db.session.commit()
        return _mfa_error_response(exc)

    log_event(
        'auth.mfa_enabled',
        'User',
        entity_id=user.id,
        actor=user,
        metadata={'recovery_codes_issued': len(recovery_codes)},
    )
    return _complete_login(
        user,
        challenge.get('ip_address') or request_ip_address(),
        challenge.get('user_agent') or request.headers.get('User-Agent'),
        mfa_verified=True,
        extra_data={'recovery_codes': recovery_codes},
    )


@auth_bp.post('/mfa/challenge/verify')
@limiter.limit('10 per minute')
def mfa_challenge_verify():
    try:
        payload = MfaChallengeSchema().load(request.get_json(silent=True) or {})
        user, method, challenge = verify_mfa_challenge(payload['challenge_token'], payload['code'])
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except MfaError as exc:
        log_event('auth.mfa_verification_failed', 'Authentication', actor=None, metadata={'reason': exc.reason})
        db.session.commit()
        return _mfa_error_response(exc)

    log_event(
        'auth.mfa_verified',
        'User',
        entity_id=user.id,
        actor=user,
        metadata={'method': method},
    )
    return _complete_login(
        user,
        challenge.get('ip_address') or request_ip_address(),
        challenge.get('user_agent') or request.headers.get('User-Agent'),
        mfa_verified=True,
    )


@auth_bp.get('/mfa/status')
@jwt_required()
def get_mfa_status():
    return success(mfa_status(current_user))


@auth_bp.post('/mfa/recovery-codes/regenerate')
@jwt_required()
@limiter.limit('5 per hour')
def regenerate_mfa_recovery_codes():
    try:
        payload = MfaRecoveryCodesSchema().load(request.get_json(silent=True) or {})
        verify_current_totp(current_user, payload['code'])
    except ValidationError as err:
        return fail('VALIDATION_ERROR', err.messages, 422)
    except MfaError as exc:
        return _mfa_error_response(exc)

    recovery_codes = generate_recovery_codes(current_user)
    log_event(
        'auth.mfa_recovery_codes_regenerated',
        'User',
        entity_id=current_user.id,
        actor=current_user,
        metadata={'recovery_codes_issued': len(recovery_codes)},
    )
    db.session.commit()
    return success({'recovery_codes': recovery_codes}, 'Recovery codes regenerated')


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
