from datetime import date, timedelta

from flask import current_app
from sqlalchemy import delete

from app.extensions import db
from app.models import MfaRecoveryCode, Notification, Tenant, User
from app.models.base import utcnow
from app.services.session_service import revoke_all_user_sessions


POLICY_MODES = {
    'optional',
    'privileged',
    'managers_and_privileged',
    'all_users',
}
PRIVILEGED_ROLES = {
    'CLIENT_ADMIN',
    'ORGANIZATION_OWNER',
    'HR_CONSULTANT',
}


def _global_required_roles() -> set[str]:
    return set(current_app.config.get('MFA_REQUIRED_ROLES') or [])


def _tenant_policy_applies(user: User, tenant: Tenant | None = None) -> bool:
    tenant = tenant or user.tenant
    if not tenant or not user.tenant_id:
        return False

    mode = tenant.mfa_policy_mode or 'optional'
    if mode == 'optional':
        return False
    if mode == 'all_users':
        return True
    if mode == 'managers_and_privileged':
        return user.has_any_role(PRIVILEGED_ROLES | {'MANAGER'})
    return user.has_any_role(PRIVILEGED_ROLES)


def _days_until(value: date | None, today: date) -> int | None:
    if value is None:
        return None
    return (value - today).days


def mfa_requirement_status(
    user: User,
    *,
    as_of_date: date | None = None,
) -> dict:
    today = as_of_date or date.today()
    tenant = user.tenant
    global_policy_applies = bool(
        _global_required_roles().intersection(user.role_names)
    )
    tenant_policy_applies = _tenant_policy_applies(user, tenant)

    enforcement_date = (
        tenant.mfa_enforcement_date
        if tenant and tenant_policy_applies
        else None
    )
    tenant_enforced = bool(
        tenant_policy_applies
        and enforcement_date
        and enforcement_date <= today
    )
    days_until_enforcement = _days_until(enforcement_date, today)
    required = global_policy_applies or tenant_enforced
    policy_applies = global_policy_applies or tenant_policy_applies
    enabled = user.mfa_enabled_at is not None

    return {
        'required': required,
        'policy_applies': policy_applies,
        'global_policy_applies': global_policy_applies,
        'tenant_policy_applies': tenant_policy_applies,
        'tenant_policy_mode': (
            tenant.mfa_policy_mode
            if tenant
            else 'platform'
        ),
        'enforcement_date': (
            enforcement_date.isoformat()
            if enforcement_date
            else None
        ),
        'days_until_enforcement': days_until_enforcement,
        'in_grace_period': bool(
            tenant_policy_applies
            and enforcement_date
            and enforcement_date > today
        ),
        'enabled': enabled,
        'compliant': enabled or not required,
        'enrollment_required': required and not enabled,
        'can_disable': not policy_applies,
    }


def tenant_mfa_policy(tenant: Tenant) -> dict:
    return {
        'tenant_id': str(tenant.id),
        'mode': tenant.mfa_policy_mode or 'optional',
        'grace_days': int(
            tenant.mfa_enrollment_grace_days
            if tenant.mfa_enrollment_grace_days is not None
            else 14
        ),
        'enforcement_date': (
            tenant.mfa_enforcement_date.isoformat()
            if tenant.mfa_enforcement_date
            else None
        ),
        'updated_at': (
            tenant.mfa_policy_updated_at.isoformat()
            if tenant.mfa_policy_updated_at
            else None
        ),
        'updated_by_user_id': (
            str(tenant.mfa_policy_updated_by_id)
            if tenant.mfa_policy_updated_by_id
            else None
        ),
        'modes': [
            {
                'value': 'optional',
                'label': 'Optional',
                'description': (
                    'Employees may enroll voluntarily. The platform '
                    'privileged-role security floor still applies.'
                ),
            },
            {
                'value': 'privileged',
                'label': 'Privileged users',
                'description': (
                    'Require MFA for client administrators, organization '
                    'owners and HR consultants.'
                ),
            },
            {
                'value': 'managers_and_privileged',
                'label': 'Managers and privileged users',
                'description': (
                    'Require MFA for managers and privileged users.'
                ),
            },
            {
                'value': 'all_users',
                'label': 'All users',
                'description': 'Require MFA for every active user.',
            },
        ],
    }


def configure_tenant_mfa_policy(
    tenant: Tenant,
    actor: User,
    payload: dict,
) -> dict:
    if (
        not actor.has_role('SUPER_ADMIN')
        and str(actor.tenant_id) != str(tenant.id)
    ):
        raise PermissionError(
            'MFA policy can only be configured within your organization'
        )

    mode = payload.get('mode', tenant.mfa_policy_mode or 'optional')
    if mode not in POLICY_MODES:
        raise ValueError('Unsupported MFA policy mode')

    grace_days = int(payload.get(
        'grace_days',
        tenant.mfa_enrollment_grace_days
        if tenant.mfa_enrollment_grace_days is not None
        else 14,
    ))
    if grace_days < 0 or grace_days > 365:
        raise ValueError('grace_days must be between 0 and 365')

    supplied_enforcement = 'enforcement_date' in payload
    enforcement_date = payload.get('enforcement_date')

    if mode == 'optional':
        enforcement_date = None
    elif not supplied_enforcement:
        if (
            tenant.mfa_policy_mode == mode
            and tenant.mfa_enforcement_date
        ):
            enforcement_date = tenant.mfa_enforcement_date
        else:
            enforcement_date = date.today() + timedelta(days=grace_days)
    elif enforcement_date is None:
        enforcement_date = date.today() + timedelta(days=grace_days)

    tenant.mfa_policy_mode = mode
    tenant.mfa_enrollment_grace_days = grace_days
    tenant.mfa_enforcement_date = enforcement_date
    tenant.mfa_policy_updated_at = utcnow()
    tenant.mfa_policy_updated_by_id = actor.id
    db.session.flush()
    return tenant_mfa_policy(tenant)


def tenant_mfa_compliance(tenant: Tenant) -> dict:
    users = User.query.filter(
        User.tenant_id == tenant.id,
        User.is_active.is_(True),
        User.deleted_at.is_(None),
    ).order_by(User.first_name.asc(), User.last_name.asc()).all()

    items = []
    for user in users:
        status = mfa_requirement_status(user)
        items.append({
            'id': str(user.id),
            'full_name': user.full_name,
            'email': user.email,
            'roles': user.role_names,
            'mfa_enabled': user.mfa_enabled_at is not None,
            'mfa_enabled_at': (
                user.mfa_enabled_at.isoformat()
                if user.mfa_enabled_at
                else None
            ),
            'mfa_reset_at': (
                user.mfa_reset_at.isoformat()
                if user.mfa_reset_at
                else None
            ),
            **status,
        })

    required_count = sum(
        1 for item in items
        if item['required']
    )
    enabled_count = sum(
        1 for item in items
        if item['mfa_enabled']
    )
    noncompliant_count = sum(
        1 for item in items
        if not item['compliant']
    )

    return {
        'policy': tenant_mfa_policy(tenant),
        'summary': {
            'total_users': len(items),
            'required_users': required_count,
            'enabled_users': enabled_count,
            'noncompliant_users': noncompliant_count,
        },
        'items': items,
    }


def clear_user_mfa(user: User, *, reset_by: User | None = None) -> None:
    user.mfa_secret_encrypted = None
    user.mfa_pending_secret_encrypted = None
    user.mfa_enabled_at = None
    user.mfa_last_used_timecode = None
    user.mfa_reset_at = utcnow() if reset_by else None
    user.mfa_reset_by_user_id = reset_by.id if reset_by else None
    db.session.execute(
        delete(MfaRecoveryCode).where(
            MfaRecoveryCode.user_id == user.id
        )
    )


def administrative_reset_mfa(
    target: User,
    actor: User,
    reason: str,
) -> dict:
    if str(target.id) == str(actor.id):
        raise ValueError(
            'Administrators cannot reset their own MFA enrollment'
        )
    if not target.tenant_id:
        raise ValueError(
            'Platform accounts cannot be reset through tenant controls'
        )
    if target.has_role('ORGANIZATION_OWNER') and not actor.has_role(
        'SUPER_ADMIN'
    ):
        raise PermissionError(
            'Only a platform super administrator can reset '
            'an organization owner MFA enrollment'
        )
    if (
        target.has_role('CLIENT_ADMIN')
        and not actor.has_any_role({
            'SUPER_ADMIN',
            'ORGANIZATION_OWNER',
        })
    ):
        raise PermissionError(
            'Only an organization owner or platform super '
            'administrator can reset a client administrator MFA enrollment'
        )
    if (
        not actor.has_role('SUPER_ADMIN')
        and str(actor.tenant_id) != str(target.tenant_id)
    ):
        raise PermissionError(
            'MFA can only be reset within your organization'
        )
    if not (
        target.mfa_enabled_at
        or target.mfa_pending_secret_encrypted
    ):
        raise ValueError('The user does not have an MFA enrollment')

    clear_user_mfa(target, reset_by=actor)
    revoked_sessions = revoke_all_user_sessions(
        target,
        'administrator_mfa_reset',
        commit=False,
    )
    db.session.add(Notification(
        tenant_id=target.tenant_id,
        user_id=target.id,
        title='Your MFA enrollment was reset',
        body=(
            'An administrator reset your authenticator enrollment. '
            'You will be asked to enroll again when required by policy.'
        ),
        notification_type='security',
    ))
    db.session.flush()

    return {
        'user_id': str(target.id),
        'mfa_enabled': False,
        'revoked_sessions': revoked_sessions,
        'reset_at': (
            target.mfa_reset_at.isoformat()
            if target.mfa_reset_at
            else None
        ),
        'reason': reason,
        'policy': mfa_requirement_status(target),
    }
