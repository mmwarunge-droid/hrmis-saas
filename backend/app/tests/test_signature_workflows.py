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
    Tenant,
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

    with app.app_context():
        tenant_name = db.session.merge(admin_user).tenant.name

    assert len(app.extensions['mail_outbox']) == 1
    message = app.extensions['mail_outbox'][0]

    assert message['to'] == signer['email']
    assert tenant_name in message['subject']
    assert 'Signature required' in message['subject']
    assert tenant_name in message['text']
    assert f'/signature-tasks/{recipient_id}' in message['text']

    assert message['html']
    assert 'Signature required' in message['html']
    assert 'Review &amp; Sign Document' in message['html']
    assert tenant_name in message['html']
    assert f'/signature-tasks/{recipient_id}' in message['html']

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
        json={'signature_name': signer['name']},
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

        notification = Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=signer['user_id'],
            notification_type='signature',
        ).one()
        assert tenant_name in notification.title
        assert notification.action_url == (
            f'/signature-tasks/{recipient_id}'
        )


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
        json={'signature_name': first['name']},
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

def test_signature_request_rejects_employee_with_cross_tenant_user_link(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    """A signer must have valid platform access in the request tenant."""
    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Signature Tenant',
            slug='foreign-signature-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'foreign.signature.user@other.test',
            'first_name': 'Foreign',
            'last_name': 'Signer',
            'password': 'StrongForeignSignerPass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]

        malformed_employee = Employee(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            employee_number='SIGN-XTENANT-001',
            first_name='Malformed',
            last_name='Signer',
            email='malformed.signer@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(malformed_employee)
        db.session.commit()

        employee_id = malformed_employee.id

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
            'subject': 'Cross-tenant signer must be rejected',
            'signing_mode': 'sequential',
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(employee_id),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )

    assert response.status_code == 400

    with app.app_context():
        assert SignatureRecipient.query.filter_by(
            employee_id=employee_id,
        ).count() == 0


def test_my_signature_tasks_ignores_cross_tenant_recipient_user_link(
    client,
    app,
    tenant,
    admin_user,
):
    """A foreign User ID on a recipient must not expose another tenant's task."""
    foreign_password = 'StrongForeignTaskPass123!'

    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Signature Task Tenant',
            slug='foreign-signature-task-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'foreign.signature.task@other.test',
            'first_name': 'Foreign',
            'last_name': 'TaskUser',
            'password': foreign_password,
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]
        foreign_email = foreign_user.email

        malformed_employee = Employee(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            employee_number='SIGN-XTENANT-002',
            first_name='Malformed',
            last_name='Task',
            email='malformed.task@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(malformed_employee)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document_id,
            created_by_id=admin_user_id,
            subject='Tenant A confidential signature task',
            signing_mode='sequential',
            status='sent',
            current_sequence=1,
            sent_at=utcnow(),
            assurance_level='standard',
        )
        db.session.add(signature_request)
        db.session.flush()

        malformed_recipient = SignatureRecipient(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            user_id=foreign_user_id,
            employee_id=malformed_employee.id,
            name=malformed_employee.full_name,
            email=malformed_employee.email,
            role_label='Employee',
            sequence=1,
            status='notified',
        )
        db.session.add(malformed_recipient)
        db.session.commit()

        recipient_id = str(malformed_recipient.id)

    _login(
        client,
        foreign_email,
        foreign_password,
    )

    response = client.get(
        '/api/signature-requests/my-tasks',
    )

    assert response.status_code == 200

    items = response.get_json()['data']['items']

    assert all(
        item['id'] != recipient_id
        for item in items
    )

def test_signature_reminder_does_not_create_cross_tenant_notification(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    """Malformed recipient.user_id must not create a cross-tenant notification."""
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-XTENANT-NOTIFY',
        email='signature.notify.local@acme.test',
        password='StrongLocalSignerPass123!',
        first_name='Local',
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

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Notification tenant-boundary test',
            'signing_mode': 'sequential',
            'due_at': due_at.isoformat(),
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

    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Signature Notification Tenant',
            slug='foreign-signature-notification-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'signature.notify.foreign@other.test',
            'first_name': 'Foreign',
            'last_name': 'NotificationUser',
            'password': 'StrongForeignNotifyPass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]

        recipient = db.session.get(
            SignatureRecipient,
            recipient_id,
        )
        recipient.user_id = foreign_user_id
        db.session.commit()

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0

    reminder_response = client.post(
        f'/api/signature-requests/{request_id}/remind',
        headers=auth_headers,
    )

    assert reminder_response.status_code == 200

    with app.app_context():
        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0

def test_signature_view_does_not_email_cross_tenant_request_creator(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    """Malformed created_by_id must not leak signature details by email."""
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-XTENANT-ADMIN-MAIL',
        email='signature.adminmail.signer@acme.test',
        password='StrongAdminMailSignerPass123!',
        first_name='MailSigner',
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

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Cross-tenant creator email boundary',
            'signing_mode': 'sequential',
            'due_at': due_at.isoformat(),
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

    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Signature Creator Tenant',
            slug='foreign-signature-creator-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'foreign.signature.creator@other.test',
            'first_name': 'Foreign',
            'last_name': 'Creator',
            'password': 'StrongForeignCreatorPass123!',
            'roles': ['CLIENT_ADMIN'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]
        foreign_email = foreign_user.email

        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        signature_request.created_by_id = foreign_user_id
        db.session.commit()

    signer_headers = _login(
        client,
        signer['email'],
        signer['password'],
    )

    app.extensions['mail_outbox'].clear()

    viewed_response = client.patch(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_id}/viewed'
        ),
        headers=signer_headers,
    )

    assert viewed_response.status_code == 200

    assert all(
        message['to'] != foreign_email
        for message in app.extensions['mail_outbox']
    )

def test_overdue_internal_signature_request_expires_before_replacement(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-EXP-001',
        email='expired.request.signer@acme.test',
        password='StrongExpiredSignerPass123!',
        first_name='Expired',
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

    initial_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Initial signature request',
            'signing_mode': 'sequential',
            'due_at': initial_due_at.isoformat(),
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

    assert initial_response.status_code == 201

    initial_data = initial_response.get_json()['data']
    initial_request_id = initial_data['id']

    expired_due_at = (
        datetime.utcnow()
        - timedelta(days=1)
    ).replace(microsecond=0)

    with app.app_context():
        initial_request = db.session.get(
            SignatureRequest,
            initial_request_id,
        )
        assert initial_request is not None
        assert initial_request.provider is None

        initial_request.due_at = expired_due_at

        for recipient in initial_request.recipients:
            recipient.due_at = expired_due_at

        assert initial_request.reminder_rule is not None
        initial_request.reminder_rule.next_run_at = expired_due_at

        db.session.commit()

    replacement_due_at = (
        datetime.utcnow()
        + timedelta(days=14)
    ).replace(microsecond=0)

    replacement_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Replacement signature request',
            'signing_mode': 'sequential',
            'due_at': replacement_due_at.isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )

    assert replacement_response.status_code == 201, (
        replacement_response.get_json()
    )

    replacement_data = replacement_response.get_json()['data']

    with app.app_context():
        initial_request = db.session.get(
            SignatureRequest,
            initial_request_id,
        )
        document = db.session.get(
            Document,
            document_id,
        )

        assert initial_request.status == 'expired'

        assert all(
            recipient.status == 'expired'
            for recipient in initial_request.recipients
        )

        assert initial_request.reminder_rule.is_active is False
        assert initial_request.reminder_rule.next_run_at is None

        event_types = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=initial_request_id,
            ).all()
        }

        assert 'signature.request_expired' in event_types

        assert replacement_data['id'] != str(initial_request.id)
        assert document.signature_status == 'pending'

def test_signature_expiry_cli_expires_overdue_internal_requests(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-EXP-CLI-001',
        email='expiry.cli.signer@acme.test',
        password='StrongExpiryCliSignerPass123!',
        first_name='ExpiryCli',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    future_due_at = (
        datetime.utcnow()
        + timedelta(days=7)
    ).replace(microsecond=0)

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Scheduled expiry regression',
            'signing_mode': 'sequential',
            'due_at': future_due_at.isoformat(),
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

    assert create_response.status_code == 201

    request_id = create_response.get_json()['data']['id']

    overdue_at = (
        datetime.utcnow()
        - timedelta(days=1)
    ).replace(microsecond=0)

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        assert signature_request.provider is None

        signature_request.due_at = overdue_at

        for recipient in signature_request.recipients:
            recipient.due_at = overdue_at

        assert signature_request.reminder_rule is not None
        signature_request.reminder_rule.next_run_at = overdue_at

        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=['signature-expiries'])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == '{"expired_requests": 1}'

    second_result = runner.invoke(args=['signature-expiries'])

    assert second_result.exit_code == 0, second_result.output
    assert second_result.output.strip() == '{"expired_requests": 0}'

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        document = db.session.get(
            Document,
            document_id,
        )

        assert signature_request.status == 'expired'

        assert all(
            recipient.status == 'expired'
            for recipient in signature_request.recipients
        )

        assert signature_request.reminder_rule.is_active is False
        assert signature_request.reminder_rule.next_run_at is None

        assert document.signature_status == 'expired'

        event_types = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=request_id,
            ).all()
        }

        assert 'signature.request_expired' in event_types


def test_client_admin_resends_expired_signature_request_with_history(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-RESEND-001',
        email='resend.signer@acme.test',
        password='StrongResendSignerPass123!',
        first_name='Resend',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    initial_due_at = (
        datetime.utcnow() + timedelta(days=7)
    ).replace(microsecond=0)

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Employment contract signature',
            'message': 'Original signing message.',
            'signing_mode': 'sequential',
            'due_at': initial_due_at.isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
                'fields': [
                    {
                        'field_type': 'signature',
                        'label': 'Employee signature',
                        'page_number': 1,
                        'x': 0.1,
                        'y': 0.7,
                        'width': 0.35,
                        'height': 0.06,
                    },
                    {
                        'field_type': 'date',
                        'label': 'Date signed',
                        'page_number': 1,
                        'x': 0.55,
                        'y': 0.7,
                        'width': 0.25,
                        'height': 0.05,
                    },
                    {
                        'field_type': 'text',
                        'label': 'Work location',
                        'placeholder': 'Enter work location',
                        'prefill_key': 'employee.email',
                        'page_number': 1,
                        'x': 0.1,
                        'y': 0.62,
                        'width': 0.35,
                        'height': 0.05,
                    },
                ],
            }],
            'reminder': {
                'first_reminder_after_days': 3,
                'reminder_interval_days': 4,
                'escalation_days_before_due': 2,
            },
        },
    )

    assert create_response.status_code == 201
    initial_data = create_response.get_json()['data']
    initial_request_id = initial_data['id']

    expired_due_at = (
        datetime.utcnow() - timedelta(days=1)
    ).replace(microsecond=0)

    with app.app_context():
        initial_request = db.session.get(
            SignatureRequest,
            initial_request_id,
        )
        initial_request.due_at = expired_due_at
        for recipient in initial_request.recipients:
            recipient.due_at = expired_due_at
        db.session.commit()

    resend_due_at = (
        datetime.utcnow() + timedelta(days=10)
    ).replace(microsecond=0)
    resend_message = (
        'Please review the same employment contract and complete '
        'your signature as soon as possible.'
    )
    outbox_before = len(app.extensions['mail_outbox'])

    resend_response = client.post(
        f'/api/signature-requests/{initial_request_id}/resend',
        headers=auth_headers,
        json={
            'due_at': resend_due_at.isoformat(),
            'message': resend_message,
        },
    )

    assert resend_response.status_code == 201, (
        resend_response.get_json()
    )
    replacement = resend_response.get_json()['data']

    assert replacement['id'] != initial_request_id
    assert replacement['document_id'] == str(document_id)
    assert replacement['subject'] == 'Employment contract signature'
    assert replacement['message'] == resend_message
    assert replacement['status'] == 'sent'
    assert replacement['resend_of_request_id'] == initial_request_id
    assert replacement['resend_attempt'] == 1
    assert replacement['recipients'][0]['employee_id'] == str(
        signer['employee_id'],
    )
    assert replacement['recipients'][0]['email'] == signer['email']
    assert len(replacement['fields']) == 3

    replacement_text_field = next(
        field
        for field in replacement['fields']
        if field['field_type'] == 'text'
    )

    assert replacement_text_field['label'] == 'Work location'
    assert (
        replacement_text_field['placeholder']
        == 'Enter work location'
    )
    assert (
        replacement_text_field['prefill_key']
        == 'employee.email'
    )

    assert replacement['reminder']['first_reminder_after_days'] == 3
    assert replacement['reminder']['reminder_interval_days'] == 4
    assert replacement['reminder']['escalation_days_before_due'] == 2

    assert len(app.extensions['mail_outbox']) == outbox_before + 1
    resend_email = app.extensions['mail_outbox'][-1]
    assert resend_email['to'] == signer['email']
    assert resend_message in resend_email['text']
    assert resend_message in resend_email['html']
    assert replacement['recipients'][0]['id'] in resend_email['text']

    with app.app_context():
        initial_request = db.session.get(
            SignatureRequest,
            initial_request_id,
        )
        replacement_request = db.session.get(
            SignatureRequest,
            replacement['id'],
        )
        document = db.session.get(Document, document_id)

        assert initial_request.status == 'expired'
        assert replacement_request.resend_of_request_id == (
            initial_request.id
        )
        assert replacement_request.resend_attempt == 1
        assert document.signature_status == 'pending'

        resend_notification = Notification.query.filter_by(
            user_id=signer['user_id'],
        ).order_by(
            Notification.created_at.desc(),
        ).first()
        assert resend_notification is not None
        assert resend_message in resend_notification.body

        initial_events = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=initial_request.id,
            ).all()
        }
        replacement_events = {
            event.event_type
            for event in SignatureEvent.query.filter_by(
                signature_request_id=replacement_request.id,
            ).all()
        }

        assert 'signature.request_expired' in initial_events
        assert 'signature.request_resent' in initial_events
        assert 'signature.request_resend_created' in replacement_events

    duplicate_response = client.post(
        f'/api/signature-requests/{initial_request_id}/resend',
        headers=auth_headers,
        json={
            'due_at': (
                datetime.utcnow() + timedelta(days=12)
            ).replace(microsecond=0).isoformat(),
            'message': resend_message,
        },
    )
    assert duplicate_response.status_code == 400
    assert 'active signature request' in (
        duplicate_response.get_json()['error']['message']
    ).lower()

    employee_headers = _login(
        client,
        signer['email'],
        signer['password'],
    )
    forbidden_response = client.post(
        f'/api/signature-requests/{initial_request_id}/resend',
        headers=employee_headers,
        json={
            'due_at': (
                datetime.utcnow() + timedelta(days=14)
            ).replace(microsecond=0).isoformat(),
            'message': resend_message,
        },
    )
    assert forbidden_response.status_code == 403


def test_super_admin_resends_signature_request_in_selected_tenant(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-RESEND-SA-001',
        email='resend.super.signer@acme.test',
        password='StrongResendSuperSignerPass123!',
        first_name='PlatformResend',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    initial_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Platform resend contract',
            'signing_mode': 'sequential',
            'due_at': (
                datetime.utcnow() + timedelta(days=7)
            ).replace(microsecond=0).isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )
    assert initial_response.status_code == 201
    request_id = initial_response.get_json()['data']['id']

    with app.app_context():
        request_obj = db.session.get(SignatureRequest, request_id)
        request_obj.status = 'cancelled'
        request_obj.cancelled_at = utcnow()
        for recipient in request_obj.recipients:
            recipient.status = 'skipped'
        db.session.commit()

        register_user({
            'email': 'signature-platform-admin@example.test',
            'first_name': 'Signature',
            'last_name': 'Platform Admin',
            'password': 'StrongSignaturePlatformPass123!',
            'roles': ['SUPER_ADMIN'],
        })

    platform_client = app.test_client()
    login = platform_client.post(
        '/api/auth/login',
        json={
            'email': 'signature-platform-admin@example.test',
            'password': 'StrongSignaturePlatformPass123!',
        },
    )
    assert login.status_code == 200
    platform_headers = _csrf_header(platform_client)

    response = platform_client.post(
        f'/api/signature-requests/{request_id}/resend'
        f'?tenant_id={tenant.id}',
        headers=platform_headers,
        json={
            'due_at': (
                datetime.utcnow() + timedelta(days=9)
            ).replace(microsecond=0).isoformat(),
            'message': 'Please complete the replacement request.',
        },
    )

    assert response.status_code == 201, response.get_json()
    data = response.get_json()['data']
    assert data['tenant_id'] == str(tenant.id)
    assert data['resend_of_request_id'] == request_id
    assert data['resend_attempt'] == 1


def test_completed_signature_request_cannot_be_resent(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
):
    signer = _create_employee_signer(
        app,
        tenant.id,
        number='SIGN-RESEND-DONE-001',
        email='resend.completed.signer@acme.test',
        password='StrongResendCompletedPass123!',
        first_name='CompletedResend',
    )
    document_id = _create_document(
        app,
        tenant.id,
        admin_user,
    )

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Completed contract',
            'signing_mode': 'sequential',
            'due_at': (
                datetime.utcnow() + timedelta(days=7)
            ).replace(microsecond=0).isoformat(),
            'recipients': [{
                'employee_id': str(signer['employee_id']),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )
    assert response.status_code == 201
    request_id = response.get_json()['data']['id']

    with app.app_context():
        request_obj = db.session.get(SignatureRequest, request_id)
        request_obj.status = 'completed'
        request_obj.completed_at = utcnow()
        request_obj.document.signature_status = 'signed'
        for recipient in request_obj.recipients:
            recipient.status = 'signed'
            recipient.signed_at = utcnow()
        db.session.commit()

    resend_response = client.post(
        f'/api/signature-requests/{request_id}/resend',
        headers=auth_headers,
        json={
            'due_at': (
                datetime.utcnow() + timedelta(days=10)
            ).replace(microsecond=0).isoformat(),
            'message': 'This should not be allowed.',
        },
    )

    assert resend_response.status_code == 400
    assert 'completed' in (
        resend_response.get_json()['error']['message']
    ).lower()
