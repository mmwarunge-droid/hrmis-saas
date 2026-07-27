from datetime import datetime, timedelta

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Employee,
    SignatureEvent,
    SignatureRecipient,
    SignatureReminderRule,
    SignatureRequest,
)


def test_signature_request_tracks_recipients_reminders_and_events(
    app,
    tenant,
    admin_user,
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        employee = Employee(
            tenant_id=tenant.id,
            employee_number='SIGN-001',
            first_name='Jane',
            last_name='Signer',
            email='jane.signer@example.com',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(employee)
        db.session.flush()

        document = Document(
            tenant_id=tenant.id,
            employee_id=employee.id,
            uploaded_by_id=admin_user_id,
            title='Employment contract',
            document_type='contract',
            original_filename='employment-contract.pdf',
            stored_filename='employment-contract-test.pdf',
            file_path='/tmp/employment-contract-test.pdf',
            mime_type='application/pdf',
            size_bytes=1024,
            checksum_sha256='a' * 64,
            signature_status='pending',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.flush()

        request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document.id,
            created_by_id=admin_user_id,
            subject='Please sign your employment contract',
            message='Review and sign before the deadline.',
            signing_mode='sequential',
            status='sent',
            due_at=datetime.utcnow() + timedelta(days=7),
        )
        db.session.add(request)
        db.session.flush()

        recipient = SignatureRecipient(
            tenant_id=tenant.id,
            signature_request_id=request.id,
            employee_id=employee.id,
            name=employee.full_name,
            email=employee.email,
            role_label='Employee',
            sequence=1,
            status='notified',
            due_at=request.due_at,
        )
        reminder = SignatureReminderRule(
            tenant_id=tenant.id,
            signature_request_id=request.id,
            first_reminder_after_days=2,
            reminder_interval_days=2,
            escalation_days_before_due=1,
        )
        event = SignatureEvent(
            tenant_id=tenant.id,
            signature_request_id=request.id,
            actor_user_id=admin_user_id,
            event_type='signature_request.created',
            description='Signature request created',
            metadata_json={'document_title': document.title},
        )

        db.session.add_all([recipient, reminder, event])
        db.session.commit()

        saved = db.session.get(SignatureRequest, request.id)
        data = saved.to_dict()

        assert data['status'] == 'sent'
        assert data['signing_mode'] == 'sequential'
        assert data['recipient_count'] == 1
        assert data['signed_count'] == 0
        assert data['recipients'][0]['email'] == employee.email
        assert saved.reminder_rule.reminder_interval_days == 2
        assert saved.events[0].event_type == (
            'signature_request.created'
        )
