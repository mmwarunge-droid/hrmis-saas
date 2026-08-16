import hashlib
import html
import secrets
from datetime import timedelta
from urllib.parse import urlencode

from flask import current_app
from sqlalchemy import select

from app.extensions import db
from app.models import AccountToken, User
from app.models.base import to_utc_naive, utcnow
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
        return timedelta(
            minutes=max(
                current_app.config['PASSWORD_RESET_TOKEN_MINUTES'],
                1,
            )
        )
    if purpose == AccountToken.PURPOSE_EMAIL_VERIFICATION:
        return timedelta(
            hours=max(
                current_app.config['EMAIL_VERIFICATION_TOKEN_HOURS'],
                1,
            )
        )
    if purpose == AccountToken.PURPOSE_ACCOUNT_INVITE:
        return timedelta(
            hours=max(
                current_app.config['ACCOUNT_INVITE_TOKEN_HOURS'],
                1,
            )
        )
    raise ValueError(f'Unsupported account token purpose: {purpose}')


def _account_url(config_key: str, raw_token: str) -> str:
    base_url = current_app.config[config_key].split('#', 1)[0]
    return f'{base_url}#{urlencode({"token": raw_token})}'


def issue_account_token(
    user: User,
    purpose: str,
) -> tuple[AccountToken, str]:
    if purpose not in AccountToken.PURPOSES:
        raise ValueError(f'Unsupported account token purpose: {purpose}')

    now = utcnow()
    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == purpose,
        AccountToken.consumed_at.is_(None),
    ).update(
        {AccountToken.consumed_at: now},
        synchronize_session=False,
    )

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
        subject='Reset your Kinetic password',
        text_body=(
            f'Hello {user.first_name},\n\n'
            'A password reset was requested for your Kinetic account. '
            f'Use this single-use link before it expires:\n\n{reset_url}\n\n'
            'If you did not request this change, you can ignore this email.'
        ),
        reply_to=current_app.config.get('MAIL_REPLY_TO'),
    )


def send_email_verification_email(user: User, raw_token: str) -> None:
    verification_url = _account_url('EMAIL_VERIFICATION_URL', raw_token)
    send_email(
        to_address=user.email,
        subject='Verify your Kinetic email address',
        text_body=(
            f'Hello {user.first_name},\n\n'
            'Verify your Kinetic email address using this single-use link:\n\n'
            f'{verification_url}\n\n'
            'If you did not expect this email, contact your Kinetic administrator.'
        ),
        reply_to=current_app.config.get('MAIL_REPLY_TO'),
    )


def send_account_invitation_email(
    user: User,
    raw_token: str,
) -> dict:
    activation_url = _account_url('ACCOUNT_INVITE_URL', raw_token)
    organization_name = (
        user.tenant.name
        if user.tenant and user.tenant.name
        else 'Kinetic'
    )
    expiry_hours = max(current_app.config['ACCOUNT_INVITE_TOKEN_HOURS'], 1)

    text_body = (
        f'Hi {user.first_name},\n\n'
        f'{organization_name} has given you access to Kinetic.\n\n'
        'For your privacy and security, your administrator has not created '
        'a password for you. Create your own private password using the '
        'secure link below:\n\n'
        f'{activation_url}\n\n'
        f'This invitation expires in {expiry_hours} hours and can only be '
        'used once.\n\n'
        'If you were not expecting this invitation, contact '
        'Career Disrupters support.\n\n'
        'Kinetic\n'
        'Supported by Career Disrupters\n'
        'careerdisrupters.com'
    )

    safe_first_name = html.escape(user.first_name)
    safe_organization = html.escape(organization_name)
    safe_activation_url = html.escape(activation_url, quote=True)
    html_body = f'''<!doctype html>
<html lang="en">
  <body style="margin:0;background:#f8fafc;font-family:Arial,sans-serif;color:#0f172a;">
    <div style="max-width:620px;margin:0 auto;padding:32px 20px;">
      <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;overflow:hidden;">
        <div style="background:#0f172a;padding:24px 30px;color:#ffffff;">
          <div style="font-size:12px;letter-spacing:.16em;text-transform:uppercase;color:#93c5fd;">Kinetic</div>
          <div style="margin-top:6px;font-size:24px;font-weight:700;">Welcome to your people platform</div>
        </div>
        <div style="padding:30px;">
          <p style="margin:0 0 16px;">Hi {safe_first_name},</p>
          <p style="margin:0 0 16px;line-height:1.6;">
            <strong>{safe_organization}</strong> has given you access to Kinetic.
          </p>
          <p style="margin:0 0 24px;line-height:1.6;color:#475569;">
            For your privacy and security, your administrator has not created a password for you.
            Create your own private password to activate your account.
          </p>
          <p style="margin:0 0 28px;">
            <a
              href="{safe_activation_url}"
              style="display:inline-block;background:#2563eb;color:#ffffff;
                     text-decoration:none;font-weight:700;padding:13px 20px;
                     border-radius:10px;"
            >
              Activate my Kinetic account
            </a>
          </p>
          <p style="margin:0 0 10px;font-size:13px;line-height:1.6;color:#64748b;">
            This invitation expires in {expiry_hours} hours and can only be used once.
          </p>
          <p style="margin:0 0 16px;font-size:13px;line-height:1.6;color:#64748b;">
            If you were not expecting this invitation, contact Career Disrupters support.
          </p>
          <p style="margin:0;font-size:12px;line-height:1.6;color:#94a3b8;">
            Kinetic &middot; Supported by Career Disrupters<br>
            careerdisrupters.com
          </p>
        </div>
      </div>
    </div>
  </body>
</html>'''

    return send_email(
        to_address=user.email,
        subject="You've been invited to Kinetic",
        text_body=text_body,
        html_body=html_body,
        reply_to=current_app.config.get('MAIL_REPLY_TO'),
    )


def _valid_account_token(
    raw_token: str,
    purpose: str,
    *,
    for_update: bool = True,
) -> AccountToken:
    if not raw_token:
        raise AccountTokenError(AccountTokenError.public_message)

    statement = select(AccountToken).where(
        AccountToken.token_hash == _hash_token(raw_token),
        AccountToken.purpose == purpose,
    )
    if for_update:
        statement = statement.with_for_update()
    account_token = db.session.execute(statement).scalar_one_or_none()

    user = account_token.user if account_token else None
    tenant_unavailable = bool(
        user
        and user.tenant_id
        and (not user.tenant or user.tenant.status != 'active')
    )
    if (
        not account_token
        or account_token.consumed_at is not None
        or to_utc_naive(account_token.expires_at) <= utcnow()
        or not user
        or not user.is_active
        or user.deleted_at is not None
        or tenant_unavailable
    ):
        raise AccountTokenError(AccountTokenError.public_message)
    return account_token


def account_invitation_context(raw_token: str) -> dict:
    account_token = _valid_account_token(
        raw_token,
        AccountToken.PURPOSE_ACCOUNT_INVITE,
        for_update=False,
    )
    user = account_token.user
    if not user.activation_required:
        raise AccountTokenError(AccountTokenError.public_message)
    return {
        'first_name': user.first_name,
        'full_name': user.full_name,
        'email': user.email,
        'organization_name': (
            user.tenant.name
            if user.tenant and user.tenant.name
            else 'Kinetic'
        ),
        'expires_at': account_token.expires_at.isoformat(),
    }


def accept_account_invitation(
    raw_token: str,
    new_password: str,
) -> tuple[User, int]:
    account_token = _valid_account_token(
        raw_token,
        AccountToken.PURPOSE_ACCOUNT_INVITE,
    )
    user = account_token.user
    if not user.activation_required:
        raise AccountTokenError(AccountTokenError.public_message)

    now = utcnow()
    user.password_hash = hash_password(new_password)
    user.activation_required = False
    user.activated_at = now
    user.email_verified_at = user.email_verified_at or now
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    account_token.consumed_at = now

    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose.in_({
            AccountToken.PURPOSE_ACCOUNT_INVITE,
            AccountToken.PURPOSE_PASSWORD_RESET,
            AccountToken.PURPOSE_EMAIL_VERIFICATION,
        }),
        AccountToken.consumed_at.is_(None),
    ).update(
        {AccountToken.consumed_at: now},
        synchronize_session=False,
    )

    revoked_count = revoke_all_user_sessions(
        user,
        'account_activated',
        commit=False,
    )
    return user, revoked_count


def reset_password_with_token(
    raw_token: str,
    new_password: str,
) -> tuple[User, int]:
    account_token = _valid_account_token(
        raw_token,
        AccountToken.PURPOSE_PASSWORD_RESET,
    )
    user = account_token.user
    if verify_password(new_password, user.password_hash):
        raise PasswordReuseError(
            'The new password must be different from the current password'
        )

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
    ).update(
        {AccountToken.consumed_at: now},
        synchronize_session=False,
    )

    revoked_count = revoke_all_user_sessions(
        user,
        'password_reset',
        commit=False,
    )
    return user, revoked_count


def verify_email_with_token(raw_token: str) -> User:
    account_token = _valid_account_token(
        raw_token,
        AccountToken.PURPOSE_EMAIL_VERIFICATION,
    )
    user = account_token.user
    now = utcnow()
    user.email_verified_at = user.email_verified_at or now
    account_token.consumed_at = now

    AccountToken.query.filter(
        AccountToken.user_id == user.id,
        AccountToken.purpose == AccountToken.PURPOSE_EMAIL_VERIFICATION,
        AccountToken.consumed_at.is_(None),
    ).update(
        {AccountToken.consumed_at: now},
        synchronize_session=False,
    )
    return user
