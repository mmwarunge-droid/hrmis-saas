import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    SignatureProviderEvent,
    SignatureRequest,
)


def _create_provider_request(
    app,
    tenant,
    admin_user,
    provider_request_id,
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Callback contract',
            document_type='contract',
            original_filename='callback-contract.pdf',
            stored_filename=(
                f'callback-{provider_request_id}.pdf'
            ),
            file_path=(
                f'/tmp/callback-{provider_request_id}.pdf'
            ),
            mime_type='application/pdf',
            size_bytes=1024,
            checksum_sha256='d' * 64,
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
            subject='Callback signature request',
            signing_mode='sequential',
            status='sent',
            due_at=datetime.utcnow() + timedelta(days=7),
            provider='dropbox_sign',
            provider_request_id=provider_request_id,
            provider_test_mode=True,
            assurance_level='standard',
        )
        db.session.add(signature_request)
        db.session.commit()

        return signature_request.id


def _callback_payload(
    *,
    api_key,
    provider_request_id,
    valid=True,
):
    event_time = str(
        int(datetime.now(timezone.utc).timestamp()),
    )
    event_type = 'signature_request_sent'
    event_hash = hmac.new(
        api_key.encode('utf-8'),
        f'{event_time}{event_type}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()

    if not valid:
        event_hash = '0' * 64

    payload = {
        'event': {
            'event_time': event_time,
            'event_type': event_type,
            'event_hash': event_hash,
            'event_metadata': {
                'related_signature_id': 'signature-123',
            },
        },
        'signature_request': {
            'signature_request_id': provider_request_id,
        },
    }

    return json.dumps(
        payload,
        separators=(',', ':'),
        sort_keys=True,
    )


def test_dropbox_sign_callback_is_verified_and_idempotent(
    client,
    app,
    tenant,
    admin_user,
):
    api_key = 'callback-test-api-key'
    provider_request_id = 'callback-request-123'

    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = (
        'callback-client-id'
    )

    request_id = _create_provider_request(
        app,
        tenant,
        admin_user,
        provider_request_id,
    )
    raw_payload = _callback_payload(
        api_key=api_key,
        provider_request_id=provider_request_id,
    )

    first = client.post(
        '/api/signature-providers/dropbox-sign/callback',
        data={'json': raw_payload},
        content_type='multipart/form-data',
    )
    second = client.post(
        '/api/signature-providers/dropbox-sign/callback',
        data={'json': raw_payload},
        content_type='multipart/form-data',
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_data(as_text=True) == (
        'Hello API Event Received'
    )
    assert second.get_data(as_text=True) == (
        'Hello API Event Received'
    )

    with app.app_context():
        events = SignatureProviderEvent.query.all()

        assert len(events) == 1
        assert str(events[0].signature_request_id) == (
            str(request_id)
        )
        assert events[0].signature_valid is True
        assert events[0].processing_status == 'processed'
        assert events[0].provider_request_id == (
            provider_request_id
        )


def test_dropbox_sign_callback_rejects_invalid_hash(
    client,
    app,
):
    api_key = 'callback-test-api-key'

    app.config['DROPBOX_SIGN_API_KEY'] = api_key
    app.config['DROPBOX_SIGN_CLIENT_ID'] = (
        'callback-client-id'
    )

    raw_payload = _callback_payload(
        api_key=api_key,
        provider_request_id='invalid-request',
        valid=False,
    )

    response = client.post(
        '/api/signature-providers/dropbox-sign/callback',
        data={'json': raw_payload},
        content_type='multipart/form-data',
    )

    assert response.status_code == 401
    assert response.get_json()['error']['code'] == (
        'INVALID_PROVIDER_CALLBACK'
    )

    with app.app_context():
        assert SignatureProviderEvent.query.count() == 0
