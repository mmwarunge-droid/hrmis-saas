from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from marshmallow import ValidationError
from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Employee,
    Notification,
    SignatureEvent,
    SignatureRequest,
    User,
)
from app.models.base import utcnow
from app.schemas.signature_schema import SignatureRequestCreateSchema
from app.services.auth_service import register_user
from app.services.document_service import can_access_document
from app.services.signature_providers.base import (
    ProviderRequestResult,
    SignatureProviderError,
)


class FakeQesProvider:
    def __init__(self, *, fail_create=False):
        self.fail_create = fail_create
        self.created = []
        self.reminded = []
        self.cancelled = []

    def create_request(self, signature_request):
        self.created.append(signature_request.id)

        if self.fail_create:
            raise SignatureProviderError(
                'Simulated provider submission failure.',
            )

        recipient = signature_request.recipients[0]
        return ProviderRequestResult(
            provider_request_id='provider-request-123',
            recipient_ids={
                recipient.email.lower(): 'provider-signature-123',
            },
            status='awaiting_signature',
            metadata={
                'is_eid': True,
                'assurance_target': 'qes',
                'assurance_confirmed': False,
            },
        )

    def send_reminder(self, signature_request):
        self.reminded.append(signature_request.id)

    def cancel_request(self, signature_request):
        self.cancelled.append(signature_request.id)


def _csrf_header(client):
    cookie = client.get_cookie('csrf_access_token')
    assert cookie is not None
    return {'X-CSRF-TOKEN': cookie.value}


def _login(client, email, password):
    response = client.post(
        '/api/auth/login',
        json={
            'email': email,
            'password': password,
        },
    )
    assert response.status_code == 200
    return _csrf_header(client)


def _create_employee_signer(
    app,
    tenant_id,
    *,
    number,
    email,
    password,
    first_name,
):
    with app.app_context():
        user = register_user({
            'tenant_id': tenant_id,
            'email': email,
            'first_name': first_name,
            'last_name': 'Signer',
            'password': password,
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        user_id = inspect(user).identity[0]

        employee = Employee(
            tenant_id=tenant_id,
            user_id=user_id,
            employee_number=number,
            first_name=first_name,
            last_name='Signer',
            email=email,
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(employee)
        db.session.commit()

        return {
            'user_id': user_id,
            'employee_id': employee.id,
            'email': email,
            'password': password,
        }


def _create_document(
    app,
    tenant_id,
    admin_user,
    *,
    suffix,
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        document = Document(
            tenant_id=tenant_id,
            uploaded_by_id=admin_user_id,
            title='Qualified employment contract',
            document_type='contract',
            original_filename=f'qualified-contract-{suffix}.pdf',
            stored_filename=f'qualified-contract-{suffix}.pdf',
            file_path=f'/tmp/qualified-contract-{suffix}.pdf',
            mime_type='application/pdf',
            size_bytes=2048,
            checksum_sha256='e' * 64,
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()
        return document.id


def _qes_payload(document_id, employee_id):
    due_at = (
        datetime.utcnow() + timedelta(days=7)
    ).replace(
        minute=43,
        second=37,
        microsecond=0,
    )

    return {
        'document_id': str(document_id),
        'subject': 'Sign the qualified employment contract',
        'message': 'Complete identity verification before signing.',
        'assurance_level': 'qes',
        'signing_mode': 'sequential',
        'due_at': due_at.isoformat(),
        'recipients': [{
            'employee_id': str(employee_id),
            'role_label': 'Employee',
            'sequence': 1,
        }],
        'reminder': {
            'first_reminder_after_days': 2,
            'reminder_interval_days': 2,
            'escalation_days_before_due': 1,
        },
    }


def test_qes_request_uses_provider_and_blocks_internal_signing(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    monkeypatch,
):
    provider = FakeQesProvider()
    app.config['SIGNATURE_PROVIDER'] = 'dropbox_sign'
    monkeypatch.setattr(
        'app.services.signature_service.get_signature_provider',
        lambda: provider,
    )
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='QES-101',
        email='qes.signer@acme.test',
        password='StrongQesPass123!',
        first_name='Qualified',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
        suffix='workflow',
    )
    app.extensions.setdefault('mail_outbox', []).clear()

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json=_qes_payload(
            document_id,
            signer['employee_id'],
        ),
    )

    assert response.status_code == 201
    request_data = response.get_json()['data']
    request_id = request_data['id']
    recipient_id = request_data['recipients'][0]['id']

    assert request_data['status'] == 'sent'
    assert request_data['provider'] == 'dropbox_sign'
    assert request_data['provider_request_id'] == (
        'provider-request-123'
    )
    assert request_data['provider_status'] == 'awaiting_signature'
    assert request_data['provider_test_mode'] is False
    assert request_data['assurance_level'] == 'qes'
    assert request_data['provider_metadata_json'][
        'assurance_confirmed'
    ] is False
    assert request_data['recipients'][0][
        'provider_recipient_id'
    ] == 'provider-signature-123'
    assert request_data['recipients'][0]['status'] == 'notified'
    assert request_data['due_at'].endswith(':00:00')
    assert len(provider.created) == 1
    assert app.extensions['mail_outbox'] == []

    employee_headers = _login(
        client,
        signer['email'],
        signer['password'],
    )
    tasks_response = client.get(
        '/api/signature-requests/my-tasks',
    )
    task = tasks_response.get_json()['data']['items'][0]
    assert task['external_signing_required'] is True
    assert task['assurance_level'] == 'qes'
    assert task['provider'] == 'dropbox_sign'

    viewed = client.patch(
        '/api/signature-requests/recipients/'
        f'{recipient_id}/viewed',
        headers=employee_headers,
    )
    signed = client.patch(
        '/api/signature-requests/recipients/'
        f'{recipient_id}/sign',
        headers=employee_headers,
    )
    declined = client.patch(
        '/api/signature-requests/recipients/'
        f'{recipient_id}/decline',
        headers=employee_headers,
        json={'reason': 'Not through Kinetic'},
    )

    assert viewed.status_code == 400
    assert signed.status_code == 400
    assert declined.status_code == 400

    admin_headers = _login(
        client,
        'admin@acme.test',
        'StrongPass123!',
    )
    reminder = client.post(
        f'/api/signature-requests/{request_id}/remind',
        headers=admin_headers,
    )
    repeated_reminder = client.post(
        f'/api/signature-requests/{request_id}/remind',
        headers=admin_headers,
    )
    deadline = client.patch(
        f'/api/signature-requests/{request_id}/deadline',
        headers=admin_headers,
        json={
            'due_at': (
                datetime.utcnow() + timedelta(days=10)
            ).isoformat(),
        },
    )
    cancellation = client.patch(
        f'/api/signature-requests/{request_id}/cancel',
        headers=admin_headers,
        json={'reason': 'Contract requires revision.'},
    )
    repeated_cancellation = client.patch(
        f'/api/signature-requests/{request_id}/cancel',
        headers=admin_headers,
        json={'reason': 'Retry cancellation.'},
    )
    duplicate = client.post(
        '/api/signature-requests',
        headers=admin_headers,
        json=_qes_payload(
            document_id,
            signer['employee_id'],
        ),
    )

    assert reminder.status_code == 200
    assert repeated_reminder.status_code == 400
    assert 'at least one hour apart' in (
        repeated_reminder.get_json()['error']['message']
    )
    assert deadline.status_code == 400
    assert 'cannot be changed after submission' in (
        deadline.get_json()['error']['message']
    )
    assert cancellation.status_code == 200
    assert cancellation.get_json()['data']['status'] == 'sent'
    assert cancellation.get_json()['data']['provider_status'] == (
        'cancellation_pending'
    )
    assert repeated_cancellation.status_code == 400
    assert duplicate.status_code == 400
    assert len(provider.reminded) == 1
    assert len(provider.cancelled) == 1
    assert app.extensions['mail_outbox'] == []

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        document = db.session.get(Document, document_id)
        signer_user = db.session.get(User, signer['user_id'])

        assert can_access_document(signer_user, document) is True
        assert signature_request.status == 'sent'
        assert signature_request.cancelled_at is None
        assert document.signature_status == 'pending'
        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=signer['user_id'],
            notification_type='signature',
        ).count() >= 3
        event_types = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=request_id,
            ).all()
        }
        assert 'signature.provider_submitted' in event_types
        assert 'signature.provider_cancel_requested' in event_types


def test_qes_provider_failure_is_persisted_and_retriable(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    monkeypatch,
):
    failing_provider = FakeQesProvider(fail_create=True)
    app.config['SIGNATURE_PROVIDER'] = 'dropbox_sign'
    monkeypatch.setattr(
        'app.services.signature_service.get_signature_provider',
        lambda: failing_provider,
    )
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='QES-201',
        email='qes.failure@acme.test',
        password='StrongQesFailure123!',
        first_name='Failure',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
        suffix='failure',
    )

    failed = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json=_qes_payload(
            document_id,
            signer['employee_id'],
        ),
    )

    assert failed.status_code == 502

    with app.app_context():
        request = SignatureRequest.query.filter_by(
            document_id=document_id,
        ).one()
        document = db.session.get(Document, document_id)

        assert request.status == 'failed'
        assert request.provider_status == 'submission_failed'
        assert request.provider_metadata_json[
            'assurance_confirmed'
        ] is False
        assert request.reminder_rule.is_active is False
        assert document.signature_status == 'not_required'
        assert any(
            event.event_type
            == 'signature.provider_submission_failed'
            for event in request.events
        )

    successful_provider = FakeQesProvider()
    monkeypatch.setattr(
        'app.services.signature_service.get_signature_provider',
        lambda: successful_provider,
    )
    retried = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json=_qes_payload(
            document_id,
            signer['employee_id'],
        ),
    )

    assert retried.status_code == 201
    assert len(successful_provider.created) == 1


def test_qes_schema_enforces_provider_constraints():
    base_payload = {
        'document_id': str(uuid4()),
        'subject': 'Qualified signature request',
        'assurance_level': 'qes',
        'signing_mode': 'sequential',
        'due_at': (
            datetime.utcnow() + timedelta(days=7)
        ).isoformat(),
        'recipients': [{
            'employee_id': str(uuid4()),
            'sequence': 1,
        }],
    }
    with_error = {
        **base_payload,
        'signing_mode': 'parallel',
        'due_at': (
            datetime.utcnow() + timedelta(days=91)
        ).isoformat(),
        'recipients': [
            *base_payload['recipients'],
            {
                'employee_id': str(uuid4()),
                'sequence': 2,
            },
        ],
    }

    with pytest.raises(ValidationError) as exc_info:
        SignatureRequestCreateSchema().load(with_error)

    assert 'recipients' in exc_info.value.messages
    assert 'signing_mode' in exc_info.value.messages
    assert 'due_at' in exc_info.value.messages
