from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from app.extensions import db
from app.models import AccountToken, AuditLog, User
from app.models.base import utcnow
from app.utils.email import EmailDeliveryError
from app.utils.security import verify_password


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _invitation_token(message):
    link = next(
        line
        for line in message['text'].splitlines()
        if line.startswith('https://')
    )
    return parse_qs(urlparse(link).fragment)['token'][0]


def _login_admin(client):
    response = client.post(
        '/api/auth/login',
        json={
            'email': 'admin@acme.test',
            'password': 'StrongPass123!',
        },
    )
    assert response.status_code == 200
    return _csrf_header(client)


def test_invited_user_creates_private_password_before_first_login(
    client,
    app,
    tenant,
    admin_user,
):
    headers = _login_admin(client)
    response = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'invitee@acme.test',
            'first_name': 'Invitee',
            'last_name': 'User',
            'roles': ['MANAGER'],
        },
    )

    assert response.status_code == 201
    body = response.get_json()['data']
    assert body['account_status'] == 'invited'
    assert body['activation_required'] is True
    assert body['invitation']['delivery'] == 'sent'
    assert body['email_verified'] is False

    message = app.extensions['mail_outbox'][-1]
    assert message['subject'] == "You've been invited to Kinetic"
    assert 'StrongPass123!' not in message['text']
    assert 'Activate my Kinetic account' in message['html']
    raw_token = _invitation_token(message)

    before_activation = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'invitee@acme.test',
            'password': 'AnythingBeforeActivation123!',
        },
    )
    assert before_activation.status_code == 401
    assert before_activation.get_json()['error']['code'] == (
        'INVALID_CREDENTIALS'
    )

    validation = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': raw_token},
    )
    assert validation.status_code == 200
    assert validation.get_json()['data']['email'] == 'invitee@acme.test'
    with app.app_context():
        invited_user = User.query.filter_by(
            email='invitee@acme.test',
        ).one()
        expected_organization_name = invited_user.tenant.name

    assert (
        validation.get_json()['data']['organization_name']
        == expected_organization_name
    )

    activation = app.test_client().post(
        '/api/auth/invitations/accept',
        json={
            'token': raw_token,
            'password': 'InviteePrivatePass456!',
        },
    )
    assert activation.status_code == 200
    assert activation.get_json()['data']['email'] == 'invitee@acme.test'

    with app.app_context():
        user = User.query.filter_by(email='invitee@acme.test').one()
        token = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
        ).one()
        assert user.activation_required is False
        assert user.account_status == 'active'
        assert user.email_verified_at is not None
        assert user.activated_at is not None
        assert token.consumed_at is not None
        assert verify_password(
            'InviteePrivatePass456!',
            user.password_hash,
        )
        assert AuditLog.query.filter_by(
            action='auth.account_activated'
        ).count() == 1

    replay = app.test_client().post(
        '/api/auth/invitations/accept',
        json={
            'token': raw_token,
            'password': 'AnotherPrivatePass789!',
        },
    )
    assert replay.status_code == 400
    assert replay.get_json()['error']['code'] == (
        'INVALID_OR_EXPIRED_INVITATION'
    )

    login = app.test_client().post(
        '/api/auth/login',
        json={
            'email': 'invitee@acme.test',
            'password': 'InviteePrivatePass456!',
        },
    )
    assert login.status_code == 200


def test_resending_invitation_invalidates_previous_link(
    client,
    app,
    admin_user,
):
    headers = _login_admin(client)
    created = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'reinvite@acme.test',
            'first_name': 'Re',
            'last_name': 'Invite',
            'roles': ['EMPLOYEE'],
        },
    )
    assert created.status_code == 201
    user_id = created.get_json()['data']['id']
    original_token = _invitation_token(app.extensions['mail_outbox'][-1])

    resent = client.post(
        f'/api/users/{user_id}/invitation/resend',
        headers=headers,
    )
    assert resent.status_code == 200
    replacement_token = _invitation_token(
        app.extensions['mail_outbox'][-1]
    )
    assert replacement_token != original_token

    old_link = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': original_token},
    )
    new_link = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': replacement_token},
    )
    assert old_link.status_code == 400
    assert new_link.status_code == 200

    with app.app_context():
        user = User.query.filter_by(email='reinvite@acme.test').one()
        tokens = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
        ).order_by(AccountToken.created_at.asc()).all()
        assert len(tokens) == 2
        assert tokens[0].consumed_at is not None
        assert tokens[1].consumed_at is None
        assert user.invitation_sent_at is not None



def test_expired_invitation_is_rejected(
    client,
    app,
    admin_user,
):
    headers = _login_admin(client)
    created = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'expired-invite@acme.test',
            'first_name': 'Expired',
            'last_name': 'Invite',
            'roles': ['EMPLOYEE'],
        },
    )
    assert created.status_code == 201
    raw_token = _invitation_token(app.extensions['mail_outbox'][-1])

    with app.app_context():
        user = User.query.filter_by(email='expired-invite@acme.test').one()
        token = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
        ).one()
        token.expires_at = utcnow() - timedelta(minutes=1)
        db.session.commit()

    validation = app.test_client().post(
        '/api/auth/invitations/validate',
        json={'token': raw_token},
    )
    assert validation.status_code == 400
    assert validation.get_json()['error']['code'] == (
        'INVALID_OR_EXPIRED_INVITATION'
    )


def test_invited_user_cannot_bypass_activation_with_password_reset(
    client,
    app,
    admin_user,
):
    headers = _login_admin(client)
    created = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'invite-reset@acme.test',
            'first_name': 'Invite',
            'last_name': 'Reset',
            'roles': ['EMPLOYEE'],
        },
    )
    assert created.status_code == 201
    outbox_count = len(app.extensions['mail_outbox'])

    response = app.test_client().post(
        '/api/auth/password/forgot',
        json={'email': 'invite-reset@acme.test'},
    )
    assert response.status_code == 202
    assert len(app.extensions['mail_outbox']) == outbox_count

    with app.app_context():
        user = User.query.filter_by(email='invite-reset@acme.test').one()
        reset_tokens = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_PASSWORD_RESET,
        ).count()
        assert reset_tokens == 0


def test_email_failure_preserves_invited_account_for_resend(
    client,
    app,
    admin_user,
    monkeypatch,
):
    headers = _login_admin(client)

    def fail_delivery(*_args, **_kwargs):
        raise EmailDeliveryError('test delivery failure')

    monkeypatch.setattr(
        'app.routes.user_routes.send_account_invitation_email',
        fail_delivery,
    )
    response = client.post(
        '/api/users',
        headers=headers,
        json={
            'email': 'delivery-failure@acme.test',
            'first_name': 'Delivery',
            'last_name': 'Failure',
            'roles': ['EMPLOYEE'],
        },
    )

    assert response.status_code == 201
    data = response.get_json()['data']
    assert data['account_status'] == 'invited'
    assert data['invitation']['delivery'] == 'failed'
    assert data['invitation']['sent_at'] is None

    with app.app_context():
        user = User.query.filter_by(
            email='delivery-failure@acme.test'
        ).one()
        assert user.activation_required is True
        assert user.invitation_sent_at is None
        active_invites = AccountToken.query.filter_by(
            user_id=user.id,
            purpose=AccountToken.PURPOSE_ACCOUNT_INVITE,
            consumed_at=None,
        ).count()
        assert active_invites == 1
