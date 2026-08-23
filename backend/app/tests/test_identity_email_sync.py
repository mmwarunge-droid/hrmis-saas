from datetime import date
from urllib.parse import parse_qs, urlparse

from app.extensions import db
from app.models import (
    AccountToken,
    AuditLog,
    AuthSession,
    Employee,
    Tenant,
    User,
)
from app.models.base import utcnow
from app.services.account_recovery_service import issue_account_token
from app.services.auth_service import (
    register_invited_user,
    register_user,
)
from app.utils.email import EmailDeliveryError


ACTIVE_PASSWORD = 'StrongIdentityPass123!'


def _token_from_message(message):
    link = next(
        line.strip()
        for line in message['text'].splitlines()
        if line.strip().startswith('https://')
    )
    return parse_qs(urlparse(link).fragment)['token'][0]


def _seed_active_linked_employee(
    app,
    tenant_id,
    *,
    email='identity-old@acme.test',
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant_id,
            'email': email,
            'first_name': 'Identity',
            'last_name': 'Active',
            'password': ACTIVE_PASSWORD,
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

        employee = Employee(
            tenant_id=tenant_id,
            user_id=user.id,
            employee_number='IDENTITY-ACTIVE-001',
            first_name='Identity',
            last_name='Active',
            email=email,
            hire_date=date(2026, 1, 1),
            job_title='Operations Analyst',
        )
        db.session.add(employee)
        db.session.commit()

        return str(user.id), str(employee.id)


def _seed_invited_linked_employee(
    app,
    tenant_id,
    *,
    email='identity-invited-old@acme.test',
):
    with app.app_context():
        user = register_invited_user({
            'tenant_id': tenant_id,
            'email': email,
            'first_name': 'Identity',
            'last_name': 'Invited',
            'roles': ['EMPLOYEE'],
        })

        employee = Employee(
            tenant_id=tenant_id,
            user_id=user.id,
            employee_number='IDENTITY-INVITED-001',
            first_name='Identity',
            last_name='Invited',
            email=email,
            hire_date=date(2026, 1, 1),
            job_title='People Coordinator',
        )
        db.session.add(employee)
        db.session.flush()

        account_token, raw_token = issue_account_token(
            user,
            AccountToken.PURPOSE_ACCOUNT_INVITE,
        )
        user.invitation_sent_at = utcnow()
        db.session.commit()

        return (
            str(user.id),
            str(employee.id),
            str(account_token.id),
            raw_token,
        )


def test_invited_employee_email_change_updates_identity_and_reissues_invitation(
    client,
    app,
    tenant,
    auth_headers,
):
    (
        user_id,
        employee_id,
        original_token_id,
        original_raw_token,
    ) = _seed_invited_linked_employee(
        app,
        tenant.id,
    )

    mail_count = len(app.extensions.get('mail_outbox', []))

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'email': 'identity-invited-new@acme.test'},
    )

    assert response.status_code == 200
    assert (
        response.get_json()['message']
        == 'Employee email updated and a new activation invitation was sent'
    )
    assert (
        response.get_json()['data']['email']
        == 'identity-invited-new@acme.test'
    )

    assert len(app.extensions.get('mail_outbox', [])) == mail_count + 1
    message = app.extensions['mail_outbox'][-1]

    assert message['to'] == 'identity-invited-new@acme.test'
    assert message['subject'] == "You've been invited to Kinetic"

    replacement_raw_token = _token_from_message(message)
    assert replacement_raw_token != original_raw_token

    # The invitation issued to the previous email must no longer work.
    old_validation = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': original_raw_token},
    )
    assert old_validation.status_code == 400

    new_validation = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': replacement_raw_token},
    )
    assert new_validation.status_code == 200
    assert (
        new_validation.get_json()['data']['email']
        == 'identity-invited-new@acme.test'
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)
        original_token = db.session.get(
            AccountToken,
            original_token_id,
        )

        assert user.email == 'identity-invited-new@acme.test'
        assert employee.email == 'identity-invited-new@acme.test'
        assert user.activation_required is True
        assert user.email_verified_at is None
        assert original_token.consumed_at is not None

        current_invites = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
        ).order_by(AccountToken.created_at.asc()).all()

        assert len(current_invites) == 2
        assert current_invites[0].consumed_at is not None
        assert current_invites[1].consumed_at is None

        assert AuditLog.query.filter_by(
            action='employee.identity_email_changed',
        ).count() == 1


def test_active_employee_email_change_is_staged_until_verification_and_revokes_sessions(
    client,
    app,
    tenant,
    auth_headers,
):
    old_email = 'identity-old@acme.test'
    new_email = 'identity-new@acme.test'

    user_id, employee_id = _seed_active_linked_employee(
        app,
        tenant.id,
        email=old_email,
    )

    # Establish a genuine active session for the employee. It must remain
    # valid while the replacement address is only pending, then be revoked
    # when ownership of the replacement address is proven.
    employee_client = app.test_client()
    login = employee_client.post(
        '/api/auth/login',
        json={
            'email': old_email,
            'password': ACTIVE_PASSWORD,
        },
    )
    assert login.status_code == 200

    with app.app_context():
        session = AuthSession.query.filter_by(
            user_id=user_id,
            revoked_at=None,
        ).one()
        session_id = str(session.id)

    mail_count = len(app.extensions.get('mail_outbox', []))

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'email': new_email},
    )

    assert response.status_code == 200

    data = response.get_json()['data']
    assert data['email'] == old_email
    assert data['pending_email'] == new_email
    assert 'current login email remains active' in (
        response.get_json()['message']
    ).lower()

    assert len(app.extensions.get('mail_outbox', [])) == mail_count + 1

    message = app.extensions['mail_outbox'][-1]
    assert message['to'] == new_email
    assert message['subject'] == 'Verify your Kinetic email address'

    verification_token = _token_from_message(message)

    # Merely requesting the change must not mutate either stored identity.
    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)
        session = db.session.get(AuthSession, session_id)

        assert user.email == old_email
        assert employee.email == old_email
        assert session.revoked_at is None

        token = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_EMAIL_VERIFICATION,
            consumed_at=None,
        ).one()

        assert token.target_email == new_email

    # Ownership of the proposed email is proven here.
    confirmation = app.test_client().post(
        '/api/auth/email-verification/confirm',
        json={'token': verification_token},
    )

    assert confirmation.status_code == 200

    confirmation_data = confirmation.get_json()['data']
    assert confirmation_data['email_verified'] is True
    assert confirmation_data['identity_email_changed'] is True
    assert confirmation_data['email'] == new_email
    assert confirmation_data['revoked_sessions'] == 1

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)
        session = db.session.get(AuthSession, session_id)

        assert user.email == new_email
        assert employee.email == new_email
        assert user.email_verified_at is not None

        assert session.revoked_at is not None
        assert session.revoked_reason == 'identity_email_changed'

        assert AccountToken.query.filter(
            AccountToken.user_id == user.id,
            AccountToken.consumed_at.is_(None),
        ).count() == 0

        assert AuditLog.query.filter_by(
            action='employee.identity_email_change_requested',
        ).count() == 1

        assert AuditLog.query.filter_by(
            action='auth.identity_email_changed',
        ).count() == 1

    # The login identifier itself has moved only after verification.
    old_login = app.test_client().post(
        '/api/auth/login',
        json={
            'email': old_email,
            'password': ACTIVE_PASSWORD,
        },
    )
    assert old_login.status_code == 401

    new_login = app.test_client().post(
        '/api/auth/login',
        json={
            'email': new_email,
            'password': ACTIVE_PASSWORD,
        },
    )
    assert new_login.status_code == 200


def test_employee_email_change_rejects_email_owned_by_user_in_another_organization(
    client,
    app,
    tenant,
    auth_headers,
):
    old_email = 'identity-source@acme.test'
    duplicate_email = 'globally-owned@example.test'

    user_id, employee_id = _seed_active_linked_employee(
        app,
        tenant.id,
        email=old_email,
    )

    with app.app_context():
        other_tenant = Tenant(
            name='Identity Other Organization',
            slug='identity-other-organization',
        )
        db.session.add(other_tenant)
        db.session.commit()

        register_user({
            'tenant_id': other_tenant.id,
            'email': duplicate_email,
            'first_name': 'Existing',
            'last_name': 'Identity',
            'password': 'StrongExistingIdentity123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

    mail_count = len(app.extensions.get('mail_outbox', []))

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'email': duplicate_email},
    )

    assert response.status_code == 409
    assert (
        response.get_json()['error']['code']
        == 'IDENTITY_EMAIL_CONFLICT'
    )

    # No verification should be sent for an address already owned anywhere
    # in the platform.
    assert len(app.extensions.get('mail_outbox', [])) == mail_count

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)

        assert user.email == old_email
        assert employee.email == old_email

        assert AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_EMAIL_VERIFICATION,
        ).count() == 0


def test_invited_email_delivery_failure_rolls_back_identity_and_preserves_previous_invitation(
    client,
    app,
    tenant,
    auth_headers,
    monkeypatch,
):
    old_email = 'identity-invited-old@acme.test'
    new_email = 'identity-invited-failed@acme.test'

    (
        user_id,
        employee_id,
        original_token_id,
        original_raw_token,
    ) = _seed_invited_linked_employee(
        app,
        tenant.id,
        email=old_email,
    )

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError('test delivery failure')

    monkeypatch.setattr(
        'app.services.employee_service.send_account_invitation_email',
        fail_delivery,
    )

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'email': new_email},
    )

    assert response.status_code == 503
    assert (
        response.get_json()['error']['code']
        == 'IDENTITY_EMAIL_DELIVERY_FAILED'
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)
        original_token = db.session.get(
            AccountToken,
            original_token_id,
        )

        # The entire attempted identity mutation must be transactional.
        assert user.email == old_email
        assert employee.email == old_email

        # The invitation that existed before the failed replacement remains
        # valid rather than stranding the invitee.
        assert original_token.consumed_at is None

        invitations = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
        ).all()

        assert len(invitations) == 1
        assert invitations[0].consumed_at is None

        assert AuditLog.query.filter_by(
            action='employee.identity_email_changed',
        ).count() == 0

    preserved = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': original_raw_token},
    )
    assert preserved.status_code == 200
    assert preserved.get_json()['data']['email'] == old_email


def test_invalid_employment_change_does_not_send_or_stage_identity_email(
    client,
    app,
    tenant,
    auth_headers,
):
    old_email = 'identity-validation-old@acme.test'
    new_email = 'identity-validation-new@acme.test'

    user_id, employee_id = _seed_active_linked_employee(
        app,
        tenant.id,
        email=old_email,
    )

    mail_count = len(app.extensions.get('mail_outbox', []))

    with app.app_context():
        user = db.session.get(User, user_id)
        assert AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_EMAIL_VERIFICATION,
        ).count() == 0

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={
            'email': new_email,
            'job_title': 'Senior Operations Analyst',
            'change_effective_date': '2099-01-01',
            'change_reason': 'Invalid future-dated promotion',
        },
    )

    assert response.status_code == 400
    assert (
        response.get_json()['error']['code']
        == 'EMPLOYEE_UPDATE_FAILED'
    )

    # Validation must fail before any externally visible email is sent.
    assert len(app.extensions.get('mail_outbox', [])) == mail_count

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)

        # The failed mixed update must leave both identity records untouched.
        assert user.email == old_email
        assert employee.email == old_email

        # Ordinary employee mutations must roll back as part of the same
        # failed transaction.
        assert employee.job_title == 'Operations Analyst'

        # No staged identity credential may survive a validation failure.
        assert AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_EMAIL_VERIFICATION,
        ).count() == 0

        assert AuditLog.query.filter_by(
            action='employee.identity_email_change_requested',
        ).count() == 0


def test_staged_email_change_rechecks_global_uniqueness_at_confirmation(
    client,
    app,
    tenant,
    auth_headers,
):
    old_email = 'identity-race-old@acme.test'
    target_email = 'identity-race-target@acme.test'

    user_id, employee_id = _seed_active_linked_employee(
        app,
        tenant.id,
        email=old_email,
    )

    response = client.patch(
        f'/api/employees/{employee_id}',
        headers=auth_headers,
        json={'email': target_email},
    )

    assert response.status_code == 200

    message = app.extensions['mail_outbox'][-1]
    verification_token = _token_from_message(message)

    with app.app_context():
        original_user = db.session.get(User, user_id)

        staged_token = AccountToken.query.filter_by(
            user_id=original_user.id,
            purpose=AccountToken.PURPOSE_EMAIL_VERIFICATION,
            consumed_at=None,
        ).one()

        staged_token_id = str(staged_token.id)

        # Simulate another account claiming the proposed address after the
        # verification email was issued but before the recipient confirms it.
        register_user({
            'tenant_id': tenant.id,
            'email': target_email,
            'first_name': 'Race',
            'last_name': 'Winner',
            'password': 'StrongRaceWinner123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

    confirmation = app.test_client().post(
        '/api/auth/email-verification/confirm',
        json={'token': verification_token},
    )

    assert confirmation.status_code == 409
    assert (
        confirmation.get_json()['error']['code']
        == 'IDENTITY_EMAIL_CONFLICT'
    )

    with app.app_context():
        user = db.session.get(User, user_id)
        employee = db.session.get(Employee, employee_id)
        staged_token = db.session.get(
            AccountToken,
            staged_token_id,
        )

        # A failed confirmation must not partially move either identity.
        assert user.email == old_email
        assert employee.email == old_email

        # The token remains unconsumed because ownership was never accepted.
        assert staged_token.consumed_at is None
        assert staged_token.target_email == target_email

        assert AuditLog.query.filter_by(
            action='auth.identity_email_changed',
        ).count() == 0
