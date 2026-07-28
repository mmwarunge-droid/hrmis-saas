from datetime import timedelta

from flask import current_app

from app.extensions import db
from app.models import (
    Document,
    Employee,
    Notification,
    SignatureEvent,
    SignatureRecipient,
    SignatureReminderRule,
    SignatureRequest,
    User,
)
from app.models.base import utcnow
from app.services.audit_service import log_event
from app.utils.email import EmailDeliveryError, send_email


FINAL_RECIPIENT_STATUSES = {
    'signed',
    'declined',
    'skipped',
    'expired',
}


def _task_url():
    return (
        current_app.config['FRONTEND_URL'].rstrip('/')
        + '/tasks'
    )


def _due_text(due_at):
    if not due_at:
        return 'No deadline specified'

    return due_at.strftime('%d %B %Y at %H:%M UTC')


def _record_event(
    signature_request,
    event_type,
    *,
    actor=None,
    recipient=None,
    description=None,
    metadata=None,
):
    event = SignatureEvent(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        recipient_id=(
            recipient.id
            if recipient
            else None
        ),
        actor_user_id=(
            actor.id
            if actor
            else None
        ),
        event_type=event_type,
        description=description,
        metadata_json=metadata or {},
        occurred_at=utcnow(),
    )
    db.session.add(event)
    return event


def _create_notification(
    tenant_id,
    user_id,
    title,
    body,
):
    if not user_id:
        return None

    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        body=body,
        notification_type='signature',
    )
    db.session.add(notification)
    return notification


def _deliver_email(
    signature_request,
    to_address,
    subject,
    body,
    *,
    recipient=None,
    failure_event='signature.email_delivery_failed',
):
    try:
        send_email(
            to_address,
            subject,
            body,
        )
        return True
    except EmailDeliveryError as exc:
        _record_event(
            signature_request,
            failure_event,
            recipient=recipient,
            description='Signature workflow email delivery failed',
            metadata={
                'recipient_email': to_address,
                'error': str(exc),
            },
        )
        return False


def _notify_recipient(
    signature_request,
    recipient,
    actor=None,
):
    document = signature_request.document

    title = f'Action required: {signature_request.subject}'
    body = (
        f'{recipient.name}, you have a document requiring '
        f'your review and signature.\n\n'
        f'Document: {document.title}\n'
        f'Due: {_due_text(recipient.due_at)}\n\n'
        f'Open ACE to review the task:\n{_task_url()}'
    )

    _create_notification(
        signature_request.tenant_id,
        recipient.user_id,
        title,
        body,
    )

    delivered = _deliver_email(
        signature_request,
        recipient.email,
        title,
        body,
        recipient=recipient,
    )

    now = utcnow()

    recipient.status = 'notified'
    recipient.notified_at = now

    _record_event(
        signature_request,
        'signature.recipient_notified',
        actor=actor,
        recipient=recipient,
        description=f'{recipient.name} was notified',
        metadata={
            'email': recipient.email,
            'sequence': recipient.sequence,
            'email_delivered': delivered,
        },
    )


def _notify_admin(
    signature_request,
    title,
    body,
    *,
    recipient=None,
):
    if not signature_request.created_by_id:
        return

    administrator = db.session.get(
        User,
        signature_request.created_by_id,
    )

    if not administrator:
        return

    _create_notification(
        signature_request.tenant_id,
        administrator.id,
        title,
        body,
    )

    _deliver_email(
        signature_request,
        administrator.email,
        title,
        body,
        recipient=recipient,
        failure_event='signature.admin_email_delivery_failed',
    )


def _active_recipients(signature_request):
    if signature_request.signing_mode == 'parallel':
        return [
            recipient
            for recipient in signature_request.recipients
            if recipient.status not in FINAL_RECIPIENT_STATUSES
        ]

    return [
        recipient
        for recipient in signature_request.recipients
        if (
            recipient.sequence
            == signature_request.current_sequence
            and recipient.status not in FINAL_RECIPIENT_STATUSES
        )
    ]


def _activate_current_sequence(
    signature_request,
    actor=None,
):
    for recipient in _active_recipients(signature_request):
        if recipient.status == 'pending':
            _notify_recipient(
                signature_request,
                recipient,
                actor=actor,
            )


def create_signature_request(
    payload,
    tenant_id,
    actor,
):
    document = Document.query.filter_by(
        id=payload['document_id'],
        tenant_id=tenant_id,
        deleted_at=None,
    ).first()

    if not document:
        raise ValueError(
            'The selected document does not exist '
            'within this organization.',
        )

    if document.status != 'active':
        raise ValueError(
            'Only active documents can be sent for signature.',
        )

    recipient_payloads = payload['recipients']
    signing_mode = payload.get(
        'signing_mode',
        'sequential',
    )

    employee_ids = [
        recipient['employee_id']
        for recipient in recipient_payloads
    ]

    if len(set(employee_ids)) != len(employee_ids):
        raise ValueError(
            'Each employee can only appear once in '
            'a signature request.',
        )

    resolved_recipients = []

    for position, recipient_payload in enumerate(
        recipient_payloads,
        start=1,
    ):
        employee = Employee.query.filter_by(
            id=recipient_payload['employee_id'],
            tenant_id=tenant_id,
            deleted_at=None,
        ).first()

        if not employee:
            raise ValueError(
                'One or more selected employees are invalid '
                'for this organization.',
            )

        if not employee.user_id:
            raise ValueError(
                f'{employee.full_name} does not yet have '
                'platform access.',
            )

        sequence = (
            1
            if signing_mode == 'parallel'
            else recipient_payload.get('sequence', position)
        )

        resolved_recipients.append({
            'employee': employee,
            'sequence': sequence,
            'role_label': (
                recipient_payload.get('role_label')
                or 'Signatory'
            ),
            'due_at': (
                recipient_payload.get('due_at')
                or payload['due_at']
            ),
        })

    first_sequence = min(
        recipient['sequence']
        for recipient in resolved_recipients
    )

    now = utcnow()

    signature_request = SignatureRequest(
        tenant_id=tenant_id,
        document_id=document.id,
        created_by_id=actor.id,
        subject=payload['subject'],
        message=payload.get('message'),
        signing_mode=signing_mode,
        status='sent',
        current_sequence=first_sequence,
        due_at=payload['due_at'],
        sent_at=now,
    )
    db.session.add(signature_request)
    db.session.flush()

    for resolved in resolved_recipients:
        employee = resolved['employee']

        recipient = SignatureRecipient(
            tenant_id=tenant_id,
            signature_request_id=signature_request.id,
            user_id=employee.user_id,
            employee_id=employee.id,
            name=employee.full_name,
            email=employee.email,
            role_label=resolved['role_label'],
            sequence=resolved['sequence'],
            status='pending',
            due_at=resolved['due_at'],
        )
        db.session.add(recipient)

    db.session.flush()

    reminder_payload = payload.get('reminder') or {}

    first_reminder_days = reminder_payload.get(
        'first_reminder_after_days',
        2,
    )

    reminder_rule = SignatureReminderRule(
        tenant_id=tenant_id,
        signature_request_id=signature_request.id,
        first_reminder_after_days=first_reminder_days,
        reminder_interval_days=reminder_payload.get(
            'reminder_interval_days',
            2,
        ),
        escalation_days_before_due=reminder_payload.get(
            'escalation_days_before_due',
        ),
        is_active=reminder_payload.get(
            'is_active',
            True,
        ),
        next_run_at=(
            now + timedelta(days=first_reminder_days)
            if reminder_payload.get('is_active', True)
            else None
        ),
    )
    db.session.add(reminder_rule)

    document.signature_status = 'pending'

    _record_event(
        signature_request,
        'signature.request_created',
        actor=actor,
        description='Signature request created',
        metadata={
            'document_id': str(document.id),
            'signing_mode': signing_mode,
            'recipient_count': len(resolved_recipients),
            'due_at': payload['due_at'].isoformat(),
        },
    )

    _activate_current_sequence(
        signature_request,
        actor=actor,
    )

    log_event(
        'signature.request_create',
        'SignatureRequest',
        signature_request.id,
        tenant_id=tenant_id,
        metadata={
            'document_id': str(document.id),
            'recipient_count': len(resolved_recipients),
        },
        actor=actor,
    )

    db.session.commit()
    return signature_request


def can_access_signature_request(
    user,
    signature_request,
):
    if user.has_role('SUPER_ADMIN'):
        return True

    if str(user.tenant_id) != str(
        signature_request.tenant_id,
    ):
        return False

    if user.has_any_role({
        'HR_CONSULTANT',
        'CLIENT_ADMIN',
    }):
        return True

    return any(
        str(recipient.user_id) == str(user.id)
        for recipient in signature_request.recipients
    )


def serialize_signature_request(
    signature_request,
    include_events=False,
):
    data = signature_request.to_dict()

    data['document'] = {
        'id': str(signature_request.document.id),
        'title': signature_request.document.title,
        'document_type': (
            signature_request.document.document_type
        ),
        'original_filename': (
            signature_request.document.original_filename
        ),
        'signature_status': (
            signature_request.document.signature_status
        ),
    }

    data['reminder'] = (
        signature_request.reminder_rule.to_dict()
        if signature_request.reminder_rule
        else None
    )

    if include_events:
        data['events'] = [
            event.to_dict()
            for event in signature_request.events
        ]

    return data


def list_signature_requests(
    user,
    *,
    tenant_id=None,
    status=None,
    document_id=None,
):
    query = SignatureRequest.query

    if not user.has_role('SUPER_ADMIN'):
        query = query.filter(
            SignatureRequest.tenant_id == user.tenant_id,
        )
    elif tenant_id:
        query = query.filter(
            SignatureRequest.tenant_id == tenant_id,
        )

    if status:
        query = query.filter(
            SignatureRequest.status == status,
        )

    if document_id:
        query = query.filter(
            SignatureRequest.document_id == document_id,
        )

    return query.order_by(
        SignatureRequest.created_at.desc(),
    ).all()


def list_my_signature_tasks(user):
    recipients = SignatureRecipient.query.filter(
        SignatureRecipient.user_id == user.id,
        SignatureRecipient.status.in_([
            'notified',
            'viewed',
        ]),
    ).order_by(
        SignatureRecipient.due_at.asc(),
    ).all()

    tasks = []

    for recipient in recipients:
        signature_request = recipient.signature_request

        tasks.append({
            **recipient.to_dict(),
            'task_type': 'document_signature',
            'subject': signature_request.subject,
            'message': signature_request.message,
            'request_status': signature_request.status,
            'signing_mode': signature_request.signing_mode,
            'document': {
                'id': str(signature_request.document.id),
                'title': signature_request.document.title,
                'document_type': (
                    signature_request.document.document_type
                ),
                'original_filename': (
                    signature_request.document.original_filename
                ),
            },
        })

    return tasks


def _require_recipient_actor(recipient, actor):
    if str(recipient.user_id) != str(actor.id):
        raise PermissionError(
            'This signature task is assigned to another user.',
        )


def mark_recipient_viewed(
    recipient,
    actor,
):
    _require_recipient_actor(recipient, actor)

    if recipient.status in FINAL_RECIPIENT_STATUSES:
        raise ValueError(
            'This signature task is already closed.',
        )

    if recipient.status == 'pending':
        raise ValueError(
            'This recipient is not yet active in the '
            'signing sequence.',
        )

    signature_request = recipient.signature_request

    if not recipient.viewed_at:
        recipient.viewed_at = utcnow()

    recipient.status = 'viewed'

    if signature_request.status == 'sent':
        signature_request.status = 'in_progress'

    _record_event(
        signature_request,
        'signature.document_viewed',
        actor=actor,
        recipient=recipient,
        description=f'{recipient.name} viewed the document',
    )

    _notify_admin(
        signature_request,
        f'Document viewed: {signature_request.subject}',
        (
            f'{recipient.name} viewed '
            f'{signature_request.document.title}.\n\n'
            f'Due: {_due_text(recipient.due_at)}'
        ),
        recipient=recipient,
    )

    db.session.commit()
    return recipient


def _all_recipients_signed(signature_request):
    return all(
        recipient.status == 'signed'
        for recipient in signature_request.recipients
    )


def _advance_sequential_request(
    signature_request,
    actor,
):
    current_sequence = signature_request.current_sequence

    current_stage = [
        recipient
        for recipient in signature_request.recipients
        if recipient.sequence == current_sequence
    ]

    if not all(
        recipient.status == 'signed'
        for recipient in current_stage
    ):
        return

    remaining_sequences = sorted({
        recipient.sequence
        for recipient in signature_request.recipients
        if recipient.status == 'pending'
    })

    if not remaining_sequences:
        return

    signature_request.current_sequence = (
        remaining_sequences[0]
    )

    _record_event(
        signature_request,
        'signature.sequence_advanced',
        actor=actor,
        description='The signing workflow advanced',
        metadata={
            'previous_sequence': current_sequence,
            'current_sequence': (
                signature_request.current_sequence
            ),
        },
    )

    _activate_current_sequence(
        signature_request,
        actor=actor,
    )


def mark_recipient_signed(
    recipient,
    actor,
):
    _require_recipient_actor(recipient, actor)

    if recipient.status not in {
        'notified',
        'viewed',
    }:
        raise ValueError(
            'This signature task cannot currently be signed.',
        )

    signature_request = recipient.signature_request
    now = utcnow()

    recipient.status = 'signed'
    recipient.signed_at = now

    if not recipient.viewed_at:
        recipient.viewed_at = now

    signature_request.status = 'in_progress'

    _record_event(
        signature_request,
        'signature.recipient_signed',
        actor=actor,
        recipient=recipient,
        description=f'{recipient.name} signed the document',
        metadata={
            'sequence': recipient.sequence,
            'signed_at': now.isoformat(),
        },
    )

    if signature_request.signing_mode == 'sequential':
        _advance_sequential_request(
            signature_request,
            actor,
        )

    if _all_recipients_signed(signature_request):
        signature_request.status = 'completed'
        signature_request.completed_at = now
        signature_request.document.signature_status = 'signed'

        if signature_request.reminder_rule:
            signature_request.reminder_rule.is_active = False
            signature_request.reminder_rule.next_run_at = None

        _record_event(
            signature_request,
            'signature.request_completed',
            actor=actor,
            recipient=recipient,
            description='All recipients completed signing',
            metadata={
                'completed_at': now.isoformat(),
            },
        )

        _notify_admin(
            signature_request,
            f'Signing completed: {signature_request.subject}',
            (
                f'All recipients have signed '
                f'{signature_request.document.title}.'
            ),
            recipient=recipient,
        )
    else:
        _notify_admin(
            signature_request,
            f'Signature received: {signature_request.subject}',
            (
                f'{recipient.name} signed '
                f'{signature_request.document.title}.\n\n'
                f'Progress: {signature_request.signed_count} '
                f'of {signature_request.recipient_count}'
            ),
            recipient=recipient,
        )

    db.session.commit()
    return recipient


def decline_signature(
    recipient,
    actor,
    reason,
):
    _require_recipient_actor(recipient, actor)

    if recipient.status not in {
        'notified',
        'viewed',
    }:
        raise ValueError(
            'This signature task cannot currently be declined.',
        )

    signature_request = recipient.signature_request
    now = utcnow()

    recipient.status = 'declined'
    recipient.declined_at = now
    recipient.decline_reason = reason

    signature_request.status = 'declined'
    signature_request.document.signature_status = 'declined'

    if signature_request.reminder_rule:
        signature_request.reminder_rule.is_active = False
        signature_request.reminder_rule.next_run_at = None

    _record_event(
        signature_request,
        'signature.recipient_declined',
        actor=actor,
        recipient=recipient,
        description=f'{recipient.name} declined to sign',
        metadata={
            'reason': reason,
            'declined_at': now.isoformat(),
        },
    )

    _notify_admin(
        signature_request,
        f'Signature declined: {signature_request.subject}',
        (
            f'{recipient.name} declined to sign '
            f'{signature_request.document.title}.\n\n'
            f'Reason: {reason}'
        ),
        recipient=recipient,
    )

    db.session.commit()
    return recipient


ACTIVE_SIGNATURE_REQUEST_STATUSES = {
    'sent',
    'in_progress',
}


def _require_active_signature_request(signature_request):
    if signature_request.status not in ACTIVE_SIGNATURE_REQUEST_STATUSES:
        raise ValueError(
            'Only active signature requests can be modified.',
        )


def send_signature_reminder(
    signature_request,
    actor,
):
    _require_active_signature_request(signature_request)

    recipients = [
        recipient
        for recipient in _active_recipients(signature_request)
        if recipient.status in {'notified', 'viewed'}
    ]

    if not recipients:
        raise ValueError(
            'No active signatories are currently available '
            'for a reminder.',
        )

    now = utcnow()

    for recipient in recipients:
        title = f'Reminder: {signature_request.subject}'
        body = (
            f'{recipient.name}, this is a reminder that '
            f'{signature_request.document.title} is waiting '
            f'for your signature.\n\n'
            f'Due: {_due_text(recipient.due_at)}\n\n'
            f'Open ACE to complete the task:\n{_task_url()}'
        )

        _create_notification(
            signature_request.tenant_id,
            recipient.user_id,
            title,
            body,
        )

        delivered = _deliver_email(
            signature_request,
            recipient.email,
            title,
            body,
            recipient=recipient,
        )

        recipient.last_reminder_at = now

        _record_event(
            signature_request,
            'signature.reminder_sent',
            actor=actor,
            recipient=recipient,
            description=(
                f'A signing reminder was sent to '
                f'{recipient.name}'
            ),
            metadata={
                'email': recipient.email,
                'sequence': recipient.sequence,
                'email_delivered': delivered,
                'sent_at': now.isoformat(),
            },
        )

    if (
        signature_request.reminder_rule
        and signature_request.reminder_rule.is_active
    ):
        signature_request.reminder_rule.next_run_at = (
            now
            + timedelta(
                days=signature_request.reminder_rule
                .reminder_interval_days,
            )
        )

    log_event(
        'signature.reminder_send',
        'SignatureRequest',
        signature_request.id,
        tenant_id=signature_request.tenant_id,
        metadata={
            'recipient_count': len(recipients),
        },
        actor=actor,
    )

    db.session.commit()
    return len(recipients)


def update_signature_deadline(
    signature_request,
    due_at,
    actor,
):
    _require_active_signature_request(signature_request)

    old_due_at = signature_request.due_at
    signature_request.due_at = due_at

    affected_recipients = [
        recipient
        for recipient in signature_request.recipients
        if recipient.status not in FINAL_RECIPIENT_STATUSES
    ]

    for recipient in affected_recipients:
        recipient.due_at = due_at

    active_recipients = [
        recipient
        for recipient in affected_recipients
        if recipient.status in {'notified', 'viewed'}
    ]

    for recipient in active_recipients:
        title = f'Deadline updated: {signature_request.subject}'
        body = (
            f'{recipient.name}, the deadline for signing '
            f'{signature_request.document.title} has changed.\n\n'
            f'New due date: {_due_text(due_at)}\n\n'
            f'Open ACE to review the task:\n{_task_url()}'
        )

        _create_notification(
            signature_request.tenant_id,
            recipient.user_id,
            title,
            body,
        )

        _deliver_email(
            signature_request,
            recipient.email,
            title,
            body,
            recipient=recipient,
        )

    _record_event(
        signature_request,
        'signature.deadline_updated',
        actor=actor,
        description='The signature deadline was changed',
        metadata={
            'previous_due_at': (
                old_due_at.isoformat()
                if old_due_at
                else None
            ),
            'new_due_at': due_at.isoformat(),
            'affected_recipient_count': len(
                affected_recipients,
            ),
        },
    )

    log_event(
        'signature.deadline_update',
        'SignatureRequest',
        signature_request.id,
        tenant_id=signature_request.tenant_id,
        metadata={
            'previous_due_at': (
                old_due_at.isoformat()
                if old_due_at
                else None
            ),
            'new_due_at': due_at.isoformat(),
        },
        actor=actor,
    )

    db.session.commit()
    return signature_request


def cancel_signature_request(
    signature_request,
    actor,
    reason,
):
    _require_active_signature_request(signature_request)

    notified_recipients = [
        recipient
        for recipient in signature_request.recipients
        if recipient.status in {'notified', 'viewed'}
    ]

    now = utcnow()

    signature_request.status = 'cancelled'
    signature_request.cancelled_at = now

    for recipient in signature_request.recipients:
        if recipient.status not in FINAL_RECIPIENT_STATUSES:
            recipient.status = 'skipped'

    if signature_request.reminder_rule:
        signature_request.reminder_rule.is_active = False
        signature_request.reminder_rule.next_run_at = None

    other_active_request = SignatureRequest.query.filter(
        SignatureRequest.id != signature_request.id,
        SignatureRequest.document_id
        == signature_request.document_id,
        SignatureRequest.status.in_(
            ACTIVE_SIGNATURE_REQUEST_STATUSES,
        ),
    ).first()

    signature_request.document.signature_status = (
        'pending'
        if other_active_request
        else 'not_required'
    )

    for recipient in notified_recipients:
        title = f'Signature request cancelled: {signature_request.subject}'
        body = (
            f'{recipient.name}, the request to sign '
            f'{signature_request.document.title} has been '
            f'cancelled.\n\n'
            f'Reason: {reason}'
        )

        _create_notification(
            signature_request.tenant_id,
            recipient.user_id,
            title,
            body,
        )

        _deliver_email(
            signature_request,
            recipient.email,
            title,
            body,
            recipient=recipient,
        )

    _record_event(
        signature_request,
        'signature.request_cancelled',
        actor=actor,
        description='The signature request was cancelled',
        metadata={
            'reason': reason,
            'cancelled_at': now.isoformat(),
        },
    )

    log_event(
        'signature.request_cancel',
        'SignatureRequest',
        signature_request.id,
        tenant_id=signature_request.tenant_id,
        metadata={
            'reason': reason,
        },
        actor=actor,
    )

    db.session.commit()
    return signature_request
