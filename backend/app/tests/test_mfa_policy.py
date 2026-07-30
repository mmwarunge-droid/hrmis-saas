from datetime import date, timedelta

import pyotp
import pytest

from app.extensions import db
from app.models import (
    AuthSession,
    MfaRecoveryCode,
    Notification,
    Tenant,
    User,
)
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.mfa_policy_service import (
    administrative_reset_mfa,
    configure_tenant_mfa_policy,
    mfa_requirement_status,
)
from app.services.mfa_service import _encrypt_secret


def _login(client, email='admin@acme.test', password='StrongPass123!'):
    return client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def test_employee_can_self_enroll_with_qr_and_recovery_codes(
    client,
    app,
    admin_user,
):
    with app.app_context():
        user = User.query.filter_by(
            email='admin@acme.test',
        ).one()
        user.email_verified_at = utcnow()
        db.session.commit()

    assert _login(client).status_code == 200
    start = client.post(
        '/api/auth/mfa/enrollment/self/start',
        json={'password': 'StrongPass123!'},
        headers=_csrf_header(client),
    )

    assert start.status_code == 200
    enrollment = start.get_json()['data']
    assert enrollment['challenge_token']
    assert enrollment['provisioning_uri'].startswith(
        'otpauth://totp/'
    )
    assert enrollment['qr_code_data_uri'].startswith(
        'data:image/svg+xml;base64,'
    )

    confirm = client.post(
        '/api/auth/mfa/enrollment/self/confirm',
        json={
            'challenge_token': enrollment['challenge_token'],
            'code': pyotp.TOTP(
                enrollment['manual_key'],
            ).now(),
        },
        headers=_csrf_header(client),
    )

    assert confirm.status_code == 200
    data = confirm.get_json()['data']
    assert data['mfa']['enabled'] is True
    assert len(data['recovery_codes']) == (
        app.config['MFA_RECOVERY_CODE_COUNT']
    )
    assert client.get_cookie(
        'access_token_cookie',
        path='/api/',
    ) is not None

    with app.app_context():
        user = User.query.filter_by(
            email='admin@acme.test',
        ).one()
        assert user.mfa_enabled_at is not None
        assert user.mfa_pending_secret_encrypted is None
        assert AuthSession.query.one().mfa_verified_at is not None


def test_all_users_policy_enforces_on_scheduled_date(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        actor = User.query.filter_by(
            email='admin@acme.test',
        ).one()
        employee = register_user({
            'tenant_id': tenant.id,
            'email': 'employee-policy@acme.test',
            'first_name': 'Policy',
            'last_name': 'Employee',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        tenant_obj = db.session.get(Tenant, tenant.id)

        policy = configure_tenant_mfa_policy(
            tenant_obj,
            actor,
            {
                'mode': 'all_users',
                'grace_days': 7,
                'enforcement_date': date.today(),
            },
        )
        db.session.commit()

        status = mfa_requirement_status(employee)
        assert policy['mode'] == 'all_users'
        assert status['required'] is True
        assert status['enrollment_required'] is True
        assert status['compliant'] is False


def test_global_privileged_floor_survives_optional_tenant_policy(
    app,
    tenant,
    admin_user,
):
    app.config['MFA_REQUIRED_ROLES'] = ['CLIENT_ADMIN']

    with app.app_context():
        actor = User.query.filter_by(
            email='admin@acme.test',
        ).one()
        tenant_obj = db.session.get(Tenant, tenant.id)
        configure_tenant_mfa_policy(
            tenant_obj,
            actor,
            {'mode': 'optional', 'grace_days': 14},
        )
        db.session.commit()

        status = mfa_requirement_status(actor)
        assert status['tenant_policy_applies'] is False
        assert status['global_policy_applies'] is True
        assert status['required'] is True
        assert status['can_disable'] is False


def test_administrator_reset_clears_mfa_and_revokes_sessions(
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        actor = User.query.filter_by(
            email='admin@acme.test',
        ).one()
        target = register_user({
            'tenant_id': tenant.id,
            'email': 'reset-target@acme.test',
            'first_name': 'Reset',
            'last_name': 'Target',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        target.mfa_secret_encrypted = _encrypt_secret(
            pyotp.random_base32()
        )
        target.mfa_enabled_at = utcnow()
        db.session.add(MfaRecoveryCode(
            user_id=target.id,
            code_hash='a' * 64,
        ))
        db.session.add(AuthSession(
            tenant_id=tenant.id,
            user_id=target.id,
            refresh_jti_hash='b' * 64,
            expires_at=utcnow() + timedelta(days=1),
            last_seen_at=utcnow(),
            mfa_verified_at=utcnow(),
        ))
        db.session.commit()

        result = administrative_reset_mfa(
            target,
            actor,
            'Employee replaced their phone',
        )
        db.session.commit()

        assert result['revoked_sessions'] == 1
        assert target.mfa_enabled_at is None
        assert target.mfa_secret_encrypted is None
        assert target.mfa_reset_by_user_id == actor.id
        assert MfaRecoveryCode.query.filter_by(
            user_id=target.id,
        ).count() == 0
        assert AuthSession.query.filter_by(
            user_id=target.id,
        ).one().revoked_at is not None
        assert Notification.query.filter_by(
            user_id=target.id,
            notification_type='security',
        ).count() == 1

        with pytest.raises(ValueError, match='own MFA'):
            administrative_reset_mfa(
                actor,
                actor,
                'Self reset attempt',
            )


def test_tenant_administrator_cannot_reset_another_tenant_user(
    client,
    app,
    admin_user,
):
    with app.app_context():
        other_tenant = Tenant(
            name='Other Ltd',
            slug='other-mfa',
        )
        db.session.add(other_tenant)
        db.session.flush()
        target = register_user({
            'tenant_id': other_tenant.id,
            'email': 'other-user@example.test',
            'first_name': 'Other',
            'last_name': 'User',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        target.mfa_secret_encrypted = _encrypt_secret(
            pyotp.random_base32()
        )
        target.mfa_enabled_at = utcnow()
        target_id = target.id
        db.session.commit()

    assert _login(client).status_code == 200
    response = client.post(
        f'/api/users/{target_id}/mfa/reset',
        json={'reason': 'Cross tenant reset attempt'},
        headers=_csrf_header(client),
    )

    assert response.status_code == 403
    assert response.get_json()['error']['code'] == 'FORBIDDEN'


def test_administrator_reset_requires_mfa_step_up(
    client,
    app,
    tenant,
    admin_user,
):
    with app.app_context():
        target = register_user({
            'tenant_id': tenant.id,
            'email': 'stepup-target@acme.test',
            'first_name': 'Stepup',
            'last_name': 'Target',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        target.mfa_secret_encrypted = _encrypt_secret(
            pyotp.random_base32()
        )
        target.mfa_enabled_at = utcnow()
        target_id = target.id
        db.session.commit()

    assert _login(client).status_code == 200
    response = client.post(
        f'/api/users/{target_id}/mfa/reset',
        json={
            'reason': 'Employee replaced their phone',
            'password': 'StrongPass123!',
            'code': '123456',
        },
        headers=_csrf_header(client),
    )

    assert response.status_code == 401
    assert response.get_json()['error']['code'] == (
        'MFA_STEP_UP_REQUIRED'
    )
