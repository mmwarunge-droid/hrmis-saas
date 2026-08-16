from app.extensions import db
from app.models import Tenant
from app.services.account_recovery_service import (
    send_account_invitation_email,
)
from app.services.auth_service import register_user


def test_account_invitation_is_tenant_aware_with_platform_support_branding(
    app,
    tenant,
):
    with app.app_context():
        tenant_record = db.session.get(Tenant, tenant.id)

        user = register_user({
            'tenant_id': tenant.id,
            'email': 'branding.invitee@example.test',
            'first_name': 'Branding',
            'last_name': 'Invitee',
            'password': 'StrongBrandingPass123!',
            'roles': ['EMPLOYEE'],
        })

        app.extensions.setdefault('mail_outbox', []).clear()

        send_account_invitation_email(
            user,
            'branding-test-token',
        )

        assert len(app.extensions['mail_outbox']) == 1
        message = app.extensions['mail_outbox'][0]

        assert tenant_record.name in message['text']
        assert tenant_record.name in (message['html'] or '')

        assert (
            f'{tenant_record.name} has given you access to Kinetic.'
            in message['text']
        )
        assert 'Career Disrupters' in message['text']
        assert 'Career Disrupters' in message['html']
