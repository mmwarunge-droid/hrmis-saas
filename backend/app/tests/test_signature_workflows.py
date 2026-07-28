from datetime import datetime, timedelta

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Employee,
    Notification,
    SignatureEvent,
    SignatureRecipient,
    SignatureRequest,
)
from app.models.base import utcnow
from app.services.auth_service import register_user


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
            'name': employee.full_name,
        }


def _create_document(
    app,
    tenant_id,
    admin_user,
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        document = Document(
            tenant_id=tenant_id,
            uploaded_by_id=admin_user_id,
            title='Employment contract',
            document_type='contract',
            original_filename='employment-contract.pdf',
            stored_filename='signature-workflow-contract.pdf',
            file_path='/tmp/signature-workflow-contract.pdf',
            mime_type='application/pdf',
            size_bytes=2048,
            checksum_sha256='b' * 64,
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()
        return document.id


def test_client_admin_sends_and_employee_completes_signature_request(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-101',
        email='signer.one@acme.test',
        password='StrongSignerPass123!',
        first_name='Alice',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    due_at = (
        datetime.utcnow()
        + timedelta(days=7)
    ).replace(microsecond=0)

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Please sign your employment contract',
            'message': 'Review all clauses before signing.',
            'signing_mode': 'sequential',
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
            }],
            'reminder': {
                'first_reminder_after_days': 2,
                'reminder_interval_days': 2,
                'escalation_days_before_due': 1,
            },
        },
    )

    assert response.status_code == 201

    request_data = response.get_json()['data']
    assert request_data['status'] == 'sent'
    assert request_data['recipient_count'] == 1
    assert request_data['recipients'][0]['status'] == (
        'notified'
    )

    request_id = request_data['id']
    recipient_id = request_data['recipients'][0]['id']

    assert len(app.extensions['mail_outbox']) == 1
    assert (
        app.extensions['mail_outbox'][0]['to']
        == signer['email']
    )
    assert (
        'Action required'
        in app.extensions['mail_outbox'][0]['subject']
    )

    employee_headers = _login(
        client,
        signer['email'],
        signer['password'],
    )

    tasks_response = client.get(
        '/api/signature-requests/my-tasks',
    )
    assert tasks_response.status_code == 200

    tasks = tasks_response.get_json()['data']['items']
    assert len(tasks) == 1
    assert tasks[0]['id'] == recipient_id
    assert tasks[0]['task_type'] == 'document_signature'

    viewed_response = client.patch(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_id}/viewed'
        ),
        headers=employee_headers,
    )
    assert viewed_response.status_code == 200

    signed_response = client.patch(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_id}/sign'
        ),
        headers=employee_headers,
    )
    assert signed_response.status_code == 200

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        document = db.session.get(
            Document,
            document_id,
        )

        assert signature_request.status == 'completed'
        assert signature_request.completed_at is not None
        assert document.signature_status == 'signed'

        event_types = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=request_id,
            ).all()
        }

        assert 'signature.request_created' in event_types
        assert 'signature.recipient_notified' in event_types
        assert 'signature.document_viewed' in event_types
        assert 'signature.recipient_signed' in event_types
        assert 'signature.request_completed' in event_types

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=signer['user_id'],
            notification_type='signature',
        ).count() == 1


def test_sequential_request_notifies_next_signer_after_first_signature(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    first = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-201',
        email='first.signer@acme.test',
        password='StrongFirstPass123!',
        first_name='First',
    )
    second = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-202',
        email='second.signer@acme.test',
        password='StrongSecondPass123!',
        first_name='Second',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    due_at = (
        datetime.utcnow()
        + timedelta(days=10)
    ).replace(microsecond=0)

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Sequential contract approval',
            'signing_mode': 'sequential',
            'due_at': due_at.isoformat(),
            'recipients': [
                {
                    'employee_id': str(first['employee_id']),
                    'role_label': 'Employee',
                    'sequence': 1,
                },
                {
                    'employee_id': str(second['employee_id']),
                    'role_label': 'Manager',
                    'sequence': 2,
                },
            ],
        },
    )

    assert response.status_code == 201

    data = response.get_json()['data']
    recipients = {
        recipient['email']: recipient
        for recipient in data['recipients']
    }

    assert recipients[first['email']]['status'] == 'notified'
    assert recipients[second['email']]['status'] == 'pending'

    initial_recipient_mail = [
        message
        for message in app.extensions['mail_outbox']
        if message['to'] in {
            first['email'],
            second['email'],
        }
    ]
    assert len(initial_recipient_mail) == 1
    assert initial_recipient_mail[0]['to'] == first['email']

    first_headers = _login(
        client,
        first['email'],
        first['password'],
    )

    sign_response = client.patch(
        (
            '/api/signature-requests/recipients/'
            f"{recipients[first['email']]['id']}/sign"
        ),
        headers=first_headers,
    )
    assert sign_response.status_code == 200

    with app.app_context():
        request_obj = db.session.get(
            SignatureRequest,
            data['id'],
        )
        second_recipient = SignatureRecipient.query.filter_by(
            id=recipients[second['email']]['id'],
        ).one()

        assert request_obj.status == 'in_progress'
        assert request_obj.current_sequence == 2
        assert second_recipient.status == 'notified'
        assert second_recipient.notified_at is not None

    second_recipient_mail = [
        message
        for message in app.extensions['mail_outbox']
        if message['to'] == second['email']
    ]

    assert len(second_recipient_mail) == 1


def test_client_admin_reminds_reschedules_and_cancels_request(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-301',
        email='managed.signer@acme.test',
        password='StrongManagedPass123!',
        first_name='Managed',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    initial_due_at = (
        datetime.utcnow()
        + timedelta(days=7)
    ).replace(microsecond=0)

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Managed signature workflow',
            'signing_mode': 'sequential',
            'due_at': initial_due_at.isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )

    assert create_response.status_code == 201

    request_data = create_response.get_json()['data']
    request_id = request_data['id']
    recipient_id = request_data['recipients'][0]['id']

    initial_outbox_size = len(
        app.extensions['mail_outbox'],
    )

    reminder_response = client.post(
        f'/api/signature-requests/{request_id}/remind',
        headers=auth_headers,
    )

    assert reminder_response.status_code == 200
    assert (
        reminder_response.get_json()['data']
        ['recipient_count']
        == 1
    )
    assert len(app.extensions['mail_outbox']) == (
        initial_outbox_size + 1
    )

    updated_due_at = (
        datetime.utcnow()
        + timedelta(days=14)
    ).replace(microsecond=0)

    deadline_response = client.patch(
        f'/api/signature-requests/{request_id}/deadline',
        headers=auth_headers,
        json={
            'due_at': updated_due_at.isoformat(),
        },
    )

    assert deadline_response.status_code == 200
    assert (
        deadline_response.get_json()['data']['due_at']
        == updated_due_at.isoformat()
    )

    cancel_response = client.patch(
        f'/api/signature-requests/{request_id}/cancel',
        headers=auth_headers,
        json={
            'reason': 'The contract requires revision.',
        },
    )

    assert cancel_response.status_code == 200
    assert (
        cancel_response.get_json()['data']['status']
        == 'cancelled'
    )

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        recipient = db.session.get(
            SignatureRecipient,
            recipient_id,
        )
        document = db.session.get(
            Document,
            document_id,
        )

        assert signature_request.status == 'cancelled'
        assert signature_request.cancelled_at is not None
        assert signature_request.due_at == updated_due_at
        assert recipient.status == 'skipped'
        assert recipient.due_at == updated_due_at
        assert recipient.last_reminder_at is not None
        assert document.signature_status == 'not_required'

        event_types = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=request_id,
            ).all()
        }

        assert 'signature.reminder_sent' in event_types
        assert 'signature.deadline_updated' in event_types
        assert 'signature.request_cancelled' in event_types
