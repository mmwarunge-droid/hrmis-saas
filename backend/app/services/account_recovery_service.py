import hashlib
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import AccountToken, User
from app.models.base import utcnow
from app.services.session_service import revoke_all_user_sessions
from app.utils.email import send_email
from app.utils.security import hash_password, verify_password


class AccountTokenError(ValueError):
    public_message = 'The token is invalid or has expired'


class PasswordReuseError(ValueError):
    pass


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def token_fingerprint(raw_token: str | None) -> str | None:
    if not raw_token:
        return None
    return _hash_token(raw_token)[:24]


def _token_lifetime(purpose: str) -> timedelta:
    if purpose == AccountToken.PURPOSE_PASSWORD_RESET:
        return timedelta(minutes=max(current_app.config['PASSWORD_RESET_TOKEN_MINUTES'], 1))
    if purpose == AccountToken.PURPOSE_EMAIL_VERIFICATION:
        return timedelta(hours=max(current_app.config['EMAIL_VERIFICATION_TOKEN_HOURS'], 1))
    raise ValueError(f'Unsupported account token purpose: {purpose}')


def _account_url(config_key: str, raw_token: str) -> str:
    base_url = current_app.config[config_key].split('#', 1)[0]
    return f'{base_url}#{urlencode({"token": raw_token})}'


def issue_account_token(user: User, purpose: str) -> tuple[AccountToken, str]:
    if purpose not in AccountToken.PURPOSES:
        raise ValueError(f'Unsupported account token purpose: {purpose}')

    now = utcnow()
    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None),
    ).update({AccountToken.consumed_at: now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    account_token = AccountToken(
        tenant_id=user.tenant_id,
        user_id=user.id,
        purpose=purpose,
        token_hash=_hash_token(raw_token),
        expires_at=now + _token_lifetime(purpose),
    )
    db.session.add(account_token)
    db.session.flush()
    return account_token, raw_token


def send_password_reset_email(user: User, raw_token: str) -> None:
    reset_url = _account_url('PASSWORD_RESET_URL', raw_token)
    send_email(
        to_address=user.email,
        subject='Reset your HRMIS password',
        text_body=(
            f'Hello {user.first_name},\n\n'
            'A password reset was requested for your HRMIS account. '
            f'Use this single-use link before it expires:\n\n{reset_url}\n\n'
            'If you did not request this change, you can ignore this email.'
        ),
    )


def send_email_verification_email(user: User, raw_token: str) -> None:
    verification_url = _account_url('EMAIL_VERIFICATION_URL', raw_token)
    send_email(
        to_address=user.email,
        subject='Verify your HRMIS email address',
        text_body=(
            f'Hello {user.first_name},\n\n'
            'Verify your HRMIS email address using this single-use link:\n\n'
            f'{verification_url}\n\n'
            'If you did not expect this email, contact your HRMIS administrator.'
        ),
    )


def _valid_account_token(raw_token: str, purpose: str) -> AccountToken:
    if not raw_token:
        raise AccountTokenError(AccountTokenError.public_message)

    account_token = db.session.execute(
        select(AccountToken)
        .where(
            AccountToken.token_hash == _hash_token(raw_token),
            AccountToken.purpose == purpose,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if (
        not account_token
        or account_token.consumed_at is not None
        or account_token.expires_at <= utcnow()
        or not account_token.user
        or not account_token.user.is_active
        or account_token.user.deleted_at is not None
    ):
        raise AccountTokenError(AccountTokenError.public_message)
    return account_token


def reset_password_with_token(raw_token: str, new_password: str) -> tuple[User, int]:
    account_token = _valid_account_token(raw_token, AccountToken.PURPOSE_PASSWORD_RESET)
    user = account_token.user
    if verify_password(new_password, user.password_hash):
        raise PasswordReuseError('The new password must be different from the current password')

    now = utcnow()
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    account_token.consumed_at = now

    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == AccountToken.PURPOSE_PASSWORD_RESET,
        AccountToken.consumed_at.is_(None),
    ).update({AccountToken.consumed_at: now}, synchronize_session=False)

    revoked_count = revoke_all_user_sessions(user, 'password_reset', commit=False)
    return user, revoked_count


def verify_email_with_token(raw_token: str) -> User:
    account_token = _valid_account_token(raw_token, AccountToken.PURPOSE_EMAIL_VERIFICATION)
    user = account_token.user
    now = utcnow()
    user.email_verified_at = user.email_verified_at or now
    account_token.consumed_at = now

    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == AccountToken.PURPOSE_EMAIL_VERIFICATION,
        AccountToken.consumed_at.is_(None),
    ).update({AccountToken.consumed_at: now}, synchronize_session=False)
    return user
