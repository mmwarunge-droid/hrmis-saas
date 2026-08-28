import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Notification,
    SignatureProviderEvent,
    SignatureRecipient,
    SignatureReminderRule,
    SignatureRequest,
    Tenant,
)

from app.models.base import utcnow
from app.services.auth_service import register_user

def _create_qes_request(
    app,
    tenant,
    admin_user,
    *,
    suffix,
    provider_request_id='provider-request-1',
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='QES callback contract',
            document_type='contract',
            original_filename=f'qes-callback-{suffix}.pdf',
            stored_filename=f'qes-callback-{suffix}.pdf',
            file_path=f'/tmp/qes-callback-{suffix}.pdf',
            mime_type='application/pdf',
            size_bytes=1024,
            checksum_sha256='f' * 64,
            signature_status='pending',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document.id,
            created_by_id=admin_user_id,
            subject='QES callback request',
            signing_mode='sequential',
            status='sent',
            due_at=datetime.utcnow() + timedelta(days=7),
            provider='dropbox_sign',
            provider_request_id=provider_request_id,
            provider_status='awaiting_signature',
            provider_test_mode=False,
            assurance_level='qes',
            provider_metadata_json={
                'assurance_target': 'qes',
                'assurance_confirmed': False,
            },
        )
        db.session.add(signature_request)
        db.session.flush()

        recipient = SignatureRecipient(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            name='Amina Otieno',
            email='amina.qes@example.test',
            role_label='Employee',
            sequence=1,
            status='notified',
            due_at=signature_request.due_at,
            provider_recipient_id='provider-signature-1',
            provider_status='awaiting_signature',
        )
        reminder = SignatureReminderRule(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            first_reminder_after_days=2,
            reminder_interval_days=2,
            is_active=True,
            next_run_at=datetime.utcnow() + timedelta(days=2),
        )
        db.session.add_all([recipient, reminder])
        db.session.commit()

        return {
            'request_id': signature_request.id,
            'document_id': document.id,
            'tenant_id': tenant.id,
        }


def _callback_payload(
    *,
    api_key,
    event_type,
    event_time,
    provider_request_id,
    provider_recipient_id='provider-signature-1',
    metadata=None,
    event_message=None,
):
    event_time_raw = str(event_time)
    event_hash = hmac.new(
        api_key.encode('utf-8'),
        f'{event_time_raw}{event_type}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    event_metadata = {
        'related_signature_id': provider_recipient_id,
    }

    if event_message:
        event_metadata['event_message'] = event_message

    payload = {
        'event': {
            'event_time': event_time_raw,
            'event_type': event_type,
            'event_hash': event_hash,
            'event_metadata': event_metadata,
        },
        'signature_request': {
            'signature_request_id': provider_request_id,
            'metadata': metadata or {},
            'signatures': [{
                'signature_id': provider_recipient_id,
                'signer_email_address': (
                    'amina.qes@example.test'
                ),
                'status_code': event_type.removeprefix(
                    'signature_request_',
                ),
            }],
        },
    }

    return json.dumps(
        payload,
        separators=(',', ':'),
        sort_keys=True,
    )


def _post_callback(client, raw_payload):
    return client.post(
        '/api/signature-providers/dropbox-sign/callback',
        data={'json': raw_payload},
        content_type='multipart/form-data',
    )


def test_qes_callbacks_are_monotonic_and_wait_for_evidence(
    client,
    app,
    tenant,
    admin_user,
):
    api_key = 'qes-callback-api-key'
    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = 'qes-client-id'
    created = _create_qes_request(
        app,
        tenant,
        admin_user,
        suffix='monotonic',
    )
    base_time = int(
        datetime.now(timezone.utc).timestamp(),
    )

    signed = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_signed',
            event_time=base_time + 2,
            provider_request_id='provider-request-1',
        ),
    )
    downloadable = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_downloadable',
            event_time=base_time + 3,
            provider_request_id='provider-request-1',
        ),
    )
    stale_viewed = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_viewed',
            event_time=base_time + 4,
            provider_request_id='provider-request-1',
        ),
    )

    assert signed.status_code == 200
    assert downloadable.status_code == 200
    assert stale_viewed.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )
        recipient = signature_request.recipients[0]
        provider_events = SignatureProviderEvent.query.filter_by(
            signature_request_id=signature_request.id,
        ).order_by(SignatureProviderEvent.event_time).all()

        assert signature_request.status == 'in_progress'
        assert signature_request.completed_at is None
        assert signature_request.provider_status == 'downloadable'
        assert signature_request.provider_downloadable_at is not None
        assert signature_request.evidence_completed_at is None
        assert signature_request.provider_metadata_json[
            'evidence_pending'
        ] is True
        assert signature_request.provider_metadata_json[
            'assurance_confirmed'
        ] is False
        assert recipient.status == 'signed'
        assert recipient.provider_status == 'signed'
        assert [
            event.processing_status
            for event in provider_events
        ] == [
            'processed',
            'processed',
            'ignored',
        ]


def test_qes_cancellation_callback_closes_request(
    client,
    app,
    tenant,
    admin_user,
):
    api_key = 'qes-callback-api-key'
    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = 'qes-client-id'
    created = _create_qes_request(
        app,
        tenant,
        admin_user,
        suffix='cancelled',
        provider_request_id='provider-request-cancel',
    )
    event_time = int(
        datetime.now(timezone.utc).timestamp(),
    )

    response = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_canceled',
            event_time=event_time,
            provider_request_id='provider-request-cancel',
        ),
    )

    assert response.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )
        document = db.session.get(
            Document,
            created['document_id'],
        )

        assert signature_request.status == 'cancelled'
        assert signature_request.cancelled_at is not None
        assert signature_request.recipients[0].status == 'skipped'
        assert signature_request.reminder_rule.is_active is False
        assert document.signature_status == 'not_required'


def test_qes_invalid_callback_records_provider_failure(
    client,
    app,
    tenant,
    admin_user,
):
    api_key = 'qes-callback-api-key'
    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = 'qes-client-id'
    created = _create_qes_request(
        app,
        tenant,
        admin_user,
        suffix='invalid',
        provider_request_id='provider-request-invalid',
    )
    event_time = int(
        datetime.now(timezone.utc).timestamp(),
    )

    response = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_invalid',
            event_time=event_time,
            provider_request_id='provider-request-invalid',
            event_message='The eID request could not be processed.',
        ),
    )

    assert response.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )
        document = db.session.get(
            Document,
            created['document_id'],
        )

        assert signature_request.status == 'failed'
        assert signature_request.provider_status == 'invalid'
        assert signature_request.provider_metadata_json[
            'provider_error'
        ] == 'The eID request could not be processed.'
        assert signature_request.reminder_rule.is_active is False
        assert document.signature_status == 'not_required'


def test_callback_metadata_recovers_provider_request_mapping(
    client,
    app,
    tenant,
    admin_user,
):
    api_key = 'qes-callback-api-key'
    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = 'qes-client-id'
    created = _create_qes_request(
        app,
        tenant,
        admin_user,
        suffix='metadata',
        provider_request_id=None,
    )
    event_time = int(
        datetime.now(timezone.utc).timestamp(),
    )

    response = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_sent',
            event_time=event_time,
            provider_request_id='provider-request-recovered',
            metadata={
                'ace_request_id': str(created['request_id']),
                'ace_tenant_id': str(created['tenant_id']),
            },
        ),
    )

    assert response.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )
        event = SignatureProviderEvent.query.filter_by(
            signature_request_id=signature_request.id,
        ).one()

        assert signature_request.provider_request_id == (
            'provider-request-recovered'
        )
        assert event.processing_status == 'processed'

def test_qes_callback_does_not_notify_cross_tenant_request_creator(
    client,
    app,
    tenant,
    admin_user,
):
    """Malformed created_by_id must not create a cross-tenant notification."""
    api_key = 'qes-cross-tenant-callback-api-key'
    provider_request_id = 'provider-request-cross-tenant-owner'

    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = 'qes-client-id'

    created = _create_qes_request(
        app,
        tenant,
        admin_user,
        suffix='cross-tenant-owner',
        provider_request_id=provider_request_id,
    )

    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Provider Owner Tenant',
            slug='foreign-provider-owner-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'foreign.provider.owner@other.test',
            'first_name': 'Foreign',
            'last_name': 'ProviderOwner',
            'password': 'StrongForeignProviderPass123!',
            'roles': ['CLIENT_ADMIN'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]

        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )
        signature_request.created_by_id = foreign_user_id
        db.session.commit()

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0

    event_time = int(
        datetime.now(timezone.utc).timestamp(),
    )

    response = _post_callback(
        client,
        _callback_payload(
            api_key=api_key,
            event_type='signature_request_downloadable',
            event_time=event_time,
            provider_request_id=provider_request_id,
        ),
    )

    assert response.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            created['request_id'],
        )

        assert signature_request.provider_status == 'downloadable'

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0