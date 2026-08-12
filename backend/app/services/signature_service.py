from datetime import timedelta

from flask import current_app

from sqlalchemy.exc import IntegrityError

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
from app.models.base import to_utc_naive, utcnow
from app.services.audit_service import log_event
from app.services.signature_providers.base import (
    SignatureProviderError,
    SignatureProviderNotConfigured,
)
from app.services.signature_evidence_service import (
    capture_source_artifact,
)
from app.services.signature_providers.registry import (
    get_signature_provider,
)
from app.utils.email import EmailDeliveryError, send_email


FINAL_RECIPIENT_STATUSES = {
    'signed',
    'declined',
    'skipped',
    'expired',
}
OPEN_SIGNATURE_REQUEST_STATUSES = {
    'draft',
    'sent',
    'in_progress',
}


def _provider_backed(signature_request):
    return (
        signature_request.provider == 'dropbox_sign'
        and signature_request.assurance_level == 'qes'
    )


def _qes_provider():
    configured = current_app.config.get(
        'SIGNATURE_PROVIDER',
        'internal',
    ).strip().lower()

    if configured != 'dropbox_sign':
        raise SignatureProviderNotConfigured(
            'QES requires SIGNATURE_PROVIDER=dropbox_sign.',
        )

    return get_signature_provider()


def _qes_deadline(value):
    due_at = to_utc_naive(value).replace(
        minute=0,
        second=0,
        microsecond=0,
    )
    now = utcnow()

    if not (
        now + timedelta(days=1)
        <= due_at
        <= now + timedelta(days=90)
    ):
        raise ValueError(
            'Dropbox Sign QES deadlines must be between '
            '1 and 90 days in the future.',
        )

    return due_at


def refresh_document_signature_status(document):
    statuses = {
        item.status
        for item in SignatureRequest.query.filter_by(
            document_id=document.id,
        ).all()
    }

    if 'completed' in statuses:
        document.signature_status = 'signed'
    elif statuses & OPEN_SIGNATURE_REQUEST_STATUSES:
        document.signature_status = 'pending'
    elif 'declined' in statuses:
        document.signature_status = 'declined'
    elif 'expired' in statuses:
        document.signature_status = 'expired'
    else:
        document.signature_status = 'not_required'

    return document.signature_status


def _task_url(recipient_id=None):
    path = f'/signature-tasks/{recipient_id}' if recipient_id else '/tasks'
    return current_app.config['FRONTEND_URL'].rstrip('/') + path


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
    *,
    action_url=None,
    metadata=None,
):
    if not user_id:
        return None

    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        body=body,
        notification_type='signature',
        action_url=action_url,
        metadata_json=metadata or {},
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
        f'Open Kinetic to review the task:\n{_task_url(recipient.id)}'
    )

    _create_notification(
        signature_request.tenant_id,
        recipient.user_id,
        title,
        body,
        action_url=f'/signature-tasks/{recipient.id}',
        metadata={
            'signature_request_id': str(signature_request.id),
            'signature_recipient_id': str(recipient.id),
            'document_id': str(signature_request.document_id),
        },
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
        action_url=f'/signature-requests?request={signature_request.id}',
        metadata={'signature_request_id': str(signature_request.id)},
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

    existing_request = SignatureRequest.query.filter(
        SignatureRequest.document_id == document.id,
        SignatureRequest.status.in_(
            OPEN_SIGNATURE_REQUEST_STATUSES,
        ),
    ).first()

    if existing_request:
        raise ValueError(
            'This document already has an active signature '
            'request.',
        )

    recipient_payloads = payload['recipients']
    signing_mode = payload.get(
        'signing_mode',
        'sequential',
    )
    assurance_level = payload.get(
        'assurance_level',
        'standard',
    )
    is_qes = assurance_level == 'qes'
    request_due_at = to_utc_naive(payload['due_at'])

    if is_qes:
        request_due_at = _qes_deadline(request_due_at)

    if is_qes and (
        len(recipient_payloads) != 1
        or signing_mode != 'sequential'
    ):
        raise ValueError(
            'QES through eID requires exactly one signer '
            'and sequential signing.',
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
                request_due_at
                if is_qes
                else to_utc_naive(
                    recipient_payload.get('due_at')
                    or request_due_at
                )
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
        status='draft' if is_qes else 'sent',
        current_sequence=first_sequence,
        due_at=request_due_at,
        sent_at=None if is_qes else now,
        provider='dropbox_sign' if is_qes else None,
        provider_status='preparing' if is_qes else None,
        provider_test_mode=False if is_qes else None,
        assurance_level=assurance_level,
        evidence_status=(
            'awaiting_provider'
            if is_qes
            else 'not_required'
        ),
        provider_metadata_json=(
            {
                'eid_required': True,
                'assurance_target': 'qes',
                'assurance_confirmed': False,
            }
            if is_qes
            else {}
        ),
    )
    db.session.add(signature_request)

    try:
        db.session.flush()
    except IntegrityError as exc:
        db.session.rollback()
        raise ValueError(
            'This document already has an active signature '
            'request.',
        ) from exc

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

    _record_event(
        signature_request,
        'signature.request_created',
        actor=actor,
        description='Signature request created',
        metadata={
            'document_id': str(document.id),
            'signing_mode': signing_mode,
            'assurance_level': assurance_level,
            'recipient_count': len(resolved_recipients),
            'due_at': request_due_at.isoformat(),
        },
    )

    if is_qes:
        capture_source_artifact(signature_request)

    document.signature_status = 'pending'

    log_event(
        'signature.request_create',
        'SignatureRequest',
        signature_request.id,
        tenant_id=tenant_id,
        metadata={
            'document_id': str(document.id),
            'assurance_level': assurance_level,
            'recipient_count': len(resolved_recipients),
            'provider': 'dropbox_sign' if is_qes else 'ace',
        },
        actor=actor,
    )

    if is_qes:
        # Commit the local request before calling the provider. The
        # provider metadata contains the Kinetic request ID, so callbacks
        # can still reconcile the request if the synchronous response
        # is interrupted.
        db.session.commit()

        try:
            provider = _qes_provider()
            result = provider.create_request(signature_request)

            provider_recipient_ids = {
                recipient.email.lower(): result.recipient_ids.get(
                    recipient.email.lower(),
                )
                for recipient in signature_request.recipients
            }

            if any(
                not provider_id
                for provider_id in provider_recipient_ids.values()
            ):
                raise SignatureProviderError(
                    'Dropbox Sign did not map the QES signer.',
                )
        except (
            SignatureProviderError,
            SignatureProviderNotConfigured,
        ) as exc:
            signature_request.status = 'failed'
            signature_request.provider_status = 'submission_failed'
            signature_request.evidence_status = 'not_required'
            signature_request.evidence_next_attempt_at = None
            signature_request.provider_metadata_json = {
                **(signature_request.provider_metadata_json or {}),
                'provider_error': str(exc),
                'assurance_confirmed': False,
            }

            if signature_request.reminder_rule:
                signature_request.reminder_rule.is_active = False
                signature_request.reminder_rule.next_run_at = None

            refresh_document_signature_status(document)
            _record_event(
                signature_request,
                'signature.provider_submission_failed',
                actor=actor,
                description='Dropbox Sign QES submission failed',
                metadata={
                    'provider': 'dropbox_sign',
                    'error': str(exc),
                },
            )
            db.session.commit()
            raise

        signature_request.provider_request_id = (
            result.provider_request_id
        )
        signature_request.provider_created_at = (
            signature_request.provider_created_at or now
        )
        signature_request.provider_metadata_json = {
            **(signature_request.provider_metadata_json or {}),
            **result.metadata,
        }

        provider_state_rank = int(
            signature_request.provider_metadata_json.get(
                'provider_state_rank',
            ) or 0,
        )

        if provider_state_rank == 0:
            signature_request.provider_status = result.status

        if signature_request.status == 'draft':
            signature_request.status = 'sent'

        signature_request.sent_at = signature_request.sent_at or now

        for recipient in signature_request.recipients:
            recipient.provider_recipient_id = (
                recipient.provider_recipient_id
                or provider_recipient_ids[recipient.email.lower()]
            )

            if not (recipient.provider_metadata_json or {}).get(
                'last_callback_event',
            ):
                recipient.provider_status = result.status

            if recipient.status == 'pending':
                recipient.status = 'notified'
                recipient.notified_at = now

            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                f'QES invitation sent: {signature_request.subject}',
                (
                    'Dropbox Sign sent an identity-verified '
                    'signing invitation to your email address. '
                    'Complete the eID process there; Kinetic cannot '
                    'record this signature directly.'
                ),
                action_url=f'/signature-tasks/{recipient.id}',
                metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
            )

        _record_event(
            signature_request,
            'signature.provider_submitted',
            actor=actor,
            description='QES request submitted to Dropbox Sign',
            metadata={
                'provider': 'dropbox_sign',
                'provider_request_id': result.provider_request_id,
                'eid_required': True,
            },
        )
        db.session.commit()
        return signature_request

    _activate_current_sequence(
        signature_request,
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
        'ORGANIZATION_OWNER',
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
            'declined',
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
            'provider': signature_request.provider,
            'provider_status': signature_request.provider_status,
            'assurance_level': (
                signature_request.assurance_level
            ),
            'external_signing_required': _provider_backed(
                signature_request,
            ),
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

    if _provider_backed(signature_request):
        raise ValueError(
            'Dropbox Sign is authoritative for QES viewing '
            'and signing activity.'
        )

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
    signature_name=None,
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

    if _provider_backed(signature_request):
        raise ValueError(
            'This QES request is completed through Dropbox '
            'Sign. Kinetic cannot record the signature directly.',
        )

    now = utcnow()

    normalized_signature_name = (signature_name or actor.full_name or '').strip()
    if len(normalized_signature_name) < 2 or len(normalized_signature_name) > 240:
        raise ValueError('A valid typed signature name is required')

    recipient.status = 'signed'
    recipient.signed_at = now
    recipient.signature_name = normalized_signature_name

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
            'signature_name': normalized_signature_name,
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

    if _provider_backed(signature_request):
        raise ValueError(
            'This QES request must be declined through Dropbox '
            'Sign so the provider evidence remains authoritative.',
        )

    now = utcnow()

    recipient.status = 'declined'
    recipient.declined_at = now
    recipient.decline_reason = reason

    signature_request.status = 'declined'
    refresh_document_signature_status(
        signature_request.document,
    )

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

    from app.services.signature_discussion_service import add_comment

    add_comment(recipient, actor, reason, commit=False, notify=False)

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

    if signature_request.provider_status == 'cancellation_pending':
        raise ValueError(
            'Dropbox Sign cancellation is already pending.',
        )

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
    provider_backed = _provider_backed(signature_request)

    if provider_backed:
        recently_reminded = any(
            recipient.last_reminder_at
            and now - recipient.last_reminder_at
            < timedelta(hours=1)
            for recipient in recipients
        )

        if recently_reminded:
            raise ValueError(
                'Dropbox Sign reminders must be at least one '
                'hour apart.',
            )

        _qes_provider().send_reminder(signature_request)

    for recipient in recipients:
        title = f'Reminder: {signature_request.subject}'

        if provider_backed:
            body = (
                f'{recipient.name}, Dropbox Sign sent another '
                'QES invitation to your email address. Complete '
                'the identity verification and signing process '
                'through that provider-hosted invitation.'
            )
            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                title,
                body,
                action_url=f'/signature-tasks/{recipient.id}',
                metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
            )
            delivered = None
        else:
            body = (
                f'{recipient.name}, this is a reminder that '
                f'{signature_request.document.title} is waiting '
                f'for your signature.\n\n'
                f'Due: {_due_text(recipient.due_at)}\n\n'
                f'Open Kinetic to complete the task:\n{_task_url(recipient.id)}'
            )
            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                title,
                body,
                action_url=f'/signature-tasks/{recipient.id}',
                metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
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
                'provider': (
                    'dropbox_sign'
                    if provider_backed
                    else 'ace'
                ),
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
            'provider': (
                'dropbox_sign'
                if provider_backed
                else 'ace'
            ),
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

    if signature_request.provider_status == 'cancellation_pending':
        raise ValueError(
            'Dropbox Sign cancellation is already pending.',
        )

    due_at = to_utc_naive(due_at)
    provider_backed = _provider_backed(signature_request)

    if provider_backed:
        raise ValueError(
            'QES deadlines cannot be changed after submission. '
            'Cancel the provider request and create a new one.',
        )
    elif due_at <= utcnow():
        raise ValueError(
            'The signature deadline must be in the future.',
        )

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

        if provider_backed:
            body = (
                f'{recipient.name}, the QES deadline for '
                f'{signature_request.document.title} changed '
                f'to {_due_text(due_at)}. Continue through the '
                'Dropbox Sign invitation in your email.'
            )
            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                title,
                body,
                action_url=f'/signature-tasks/{recipient.id}',
                metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
            )
        else:
            body = (
                f'{recipient.name}, the deadline for signing '
                f'{signature_request.document.title} has changed.'
                f'\n\nNew due date: {_due_text(due_at)}\n\n'
                f'Open Kinetic to review the task:\n{_task_url(recipient.id)}'
            )
            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                title,
                body,
                action_url=f'/signature-tasks/{recipient.id}',
                metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
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
            'provider': (
                'dropbox_sign'
                if provider_backed
                else 'ace'
            ),
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
            'provider': (
                'dropbox_sign'
                if provider_backed
                else 'ace'
            ),
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

    if signature_request.provider_status == 'cancellation_pending':
        raise ValueError(
            'Dropbox Sign cancellation is already pending.',
        )

    notified_recipients = [
        recipient
        for recipient in signature_request.recipients
        if recipient.status in {'notified', 'viewed'}
    ]

    now = utcnow()

    if _provider_backed(signature_request):
        _qes_provider().cancel_request(signature_request)
        signature_request.provider_status = (
            'cancellation_pending'
        )

        if signature_request.reminder_rule:
            signature_request.reminder_rule.is_active = False
            signature_request.reminder_rule.next_run_at = None

        for recipient in notified_recipients:
            _create_notification(
                signature_request.tenant_id,
                recipient.user_id,
                (
                    'QES cancellation requested: '
                    f'{signature_request.subject}'
                ),
                (
                    'Kinetic asked Dropbox Sign to cancel the QES '
                    'request. The request remains active until '
                    'the provider confirms cancellation.'
                ),
            )

        _record_event(
            signature_request,
            'signature.provider_cancel_requested',
            actor=actor,
            description=(
                'Dropbox Sign cancellation was requested'
            ),
            metadata={
                'reason': reason,
                'requested_at': now.isoformat(),
                'provider': 'dropbox_sign',
            },
        )

        log_event(
            'signature.request_cancel',
            'SignatureRequest',
            signature_request.id,
            tenant_id=signature_request.tenant_id,
            metadata={
                'reason': reason,
                'provider': 'dropbox_sign',
                'provider_status': 'cancellation_pending',
            },
            actor=actor,
        )

        db.session.commit()
        return signature_request

    signature_request.status = 'cancelled'
    signature_request.cancelled_at = now

    for recipient in signature_request.recipients:
        if recipient.status not in FINAL_RECIPIENT_STATUSES:
            recipient.status = 'skipped'

    if signature_request.reminder_rule:
        signature_request.reminder_rule.is_active = False
        signature_request.reminder_rule.next_run_at = None

    refresh_document_signature_status(
        signature_request.document,
    )

    for recipient in notified_recipients:
        title = (
            'Signature request cancelled: '
            f'{signature_request.subject}'
        )
        body = (
            f'{recipient.name}, the request to sign '
            f'{signature_request.document.title} has been '
            f'cancelled.\n\nReason: {reason}'
        )

        _create_notification(
            signature_request.tenant_id,
            recipient.user_id,
            title,
            body,
            action_url=f'/signature-tasks/{recipient.id}',
            metadata={'signature_request_id': str(signature_request.id), 'signature_recipient_id': str(recipient.id)},
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
