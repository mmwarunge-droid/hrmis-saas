from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import User
from app.models.base import utcnow
from app.services.rbac_service import seed_roles_permissions, set_user_roles
from app.utils.security import hash_password, verify_password

# Valid bcrypt hash used only to make unknown-account checks perform password work.
_DUMMY_PASSWORD_HASH = '$2b$12$ceijpGRqAuJ.6J6AFAKfZOY49SztrsSyx8ZoOO4fdPtgFzsj7XK4e'


class AuthenticationError(ValueError):
    public_message = 'Invalid email or password'

    def __init__(self, reason: str, user: User | None = None, newly_locked: bool = False):
        super().__init__(self.public_message)
        self.reason = reason
        self.user = user
        self.newly_locked = newly_locked


def claims_for(user: User) -> dict:
    return {
        'tenant_id': str(user.tenant_id) if user.tenant_id else None,
        'roles': user.role_names,
        'permissions': user.permission_codes,
    }


def register_user(payload: dict, actor=None) -> User:
    if User.query.filter_by(email=payload['email'].lower()).first():
        raise ValueError('Email is already registered')
    seed_roles_permissions(commit=False)
    user = User(
        tenant_id=payload.get('tenant_id'),
        email=payload['email'].lower(),
        first_name=payload['first_name'],
        last_name=payload['last_name'],
        password_hash=hash_password(payload['password']),
    )
    db.session.add(user)
    db.session.flush()
    set_user_roles(user, payload.get('roles') or ['EMPLOYEE'], assigned_by_id=getattr(actor, 'id', None))
    db.session.commit()
    return user


def _reset_expired_lock(user: User, now) -> None:
    if user.locked_until and user.locked_until <= now:
        user.failed_login_attempts = 0
        user.last_failed_login_at = None
        user.locked_until = None


def _record_failed_login(user: User, now) -> bool:
    failure_window = timedelta(minutes=max(current_app.config['AUTH_FAILURE_WINDOW_MINUTES'], 1))
    if not user.last_failed_login_at or now - user.last_failed_login_at > failure_window:
        user.failed_login_attempts = 0

    user.failed_login_attempts += 1
    user.last_failed_login_at = now

    threshold = max(current_app.config['AUTH_MAX_FAILED_ATTEMPTS'], 1)
    newly_locked = user.failed_login_attempts >= threshold
    if newly_locked:
        lockout = timedelta(minutes=max(current_app.config['AUTH_LOCKOUT_MINUTES'], 1))
        user.locked_until = now + lockout

    db.session.commit()
    return newly_locked


def authenticate(email: str, password: str) -> User:
    normalized_email = email.strip().lower()
    user = User.query.filter(User.email == normalized_email, User.deleted_at.is_(None)).first()
    now = utcnow()

    if not user:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        raise AuthenticationError('invalid_credentials')

    _reset_expired_lock(user, now)

    if user.locked_until and user.locked_until > now:
        verify_password(password, user.password_hash)
        raise AuthenticationError('account_locked', user=user)

    password_valid = verify_password(password, user.password_hash)
    if not user.is_active:
        raise AuthenticationError('inactive_account', user=user)

    if not password_valid:
        newly_locked = _record_failed_login(user, now)
        reason = 'account_locked' if newly_locked else 'invalid_credentials'
        raise AuthenticationError(reason, user=user, newly_locked=newly_locked)

    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    user.last_login_at = now
    db.session.commit()
    return user
