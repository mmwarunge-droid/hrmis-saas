from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    Notification,
    SignatureEvent,
    SignatureProviderEvent,
    SignatureRecipient,
    SignatureRequest,
)
from app.models.base import utcnow
from app.services.signature_providers.registry import (
    get_signature_provider,
)


KNOWN_EVENTS = {
    'signature_request_sent',
    'signature_request_prepared',
    'signature_request_viewed',
    'signature_request_signed',
    'signature_request_all_signed',
    'signature_request_downloadable',
    'signature_request_declined',
    'signature_request_remind',
    'signature_request_canceled',
    'signature_request_expired',
    'signature_request_email_bounce',
    'signature_request_invalid',
}
STATE_EVENT_RANK = {
    'signature_request_sent': 10,
    'signature_request_prepared': 20,
    'signature_request_viewed': 30,
    'signature_request_signed': 40,
    'signature_request_all_signed': 50,
    'signature_request_downloadable': 60,
    'signature_request_declined': 60,
    'signature_request_canceled': 60,
    'signature_request_expired': 60,
    'signature_request_invalid': 60,
}
TERMINAL_REQUEST_STATUSES = {
    'completed',
    'declined',
    'expired',
    'cancelled',
    'failed',
}
def _callback_time(callback):
    return callback.event_time or utcnow()


def _payload_request(callback):
    return callback.payload.get('signature_request') or {}


def _payload_signatures(callback):
    return _payload_request(callback).get('signatures') or []


def _event_message(callback):
    return (
        callback.payload.get('event', {})
        .get('event_metadata', {})
        .get('event_message')
    )


def _recipient_for_callback(signature_request, callback):
    if callback.provider_recipient_id:
        recipient = SignatureRecipient.query.filter_by(
            signature_request_id=signature_request.id,
            provider_recipient_id=callback.provider_recipient_id,
        ).first()

        if recipient:
            return recipient

    for signature in _payload_signatures(callback):
        signature_id = signature.get('signature_id')

        if (
            callback.provider_recipient_id
            and signature_id != callback.provider_recipient_id
        ):
            continue

        email = signature.get('signer_email_address')

        if not email:
            continue

        recipient = SignatureRecipient.query.filter(
            SignatureRecipient.signature_request_id
            == signature_request.id,
            db.func.lower(SignatureRecipient.email)
            == email.lower(),
        ).first()

        if recipient:
            if signature_id and not recipient.provider_recipient_id:
                recipient.provider_recipient_id = signature_id
            return recipient

    if len(signature_request.recipients) == 1:
        recipient = signature_request.recipients[0]

        if (
            callback.provider_recipient_id
            and not recipient.provider_recipient_id
        ):
            recipient.provider_recipient_id = (
                callback.provider_recipient_id
            )

        return recipient

    return None


def _provider_status(callback):
    return callback.event_type.removeprefix(
        'signature_request_',
    )


def _parse_iso(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _can_apply_state(signature_request, callback):
    event_type = callback.event_type

    if event_type not in STATE_EVENT_RANK:
        return True

    if signature_request.status in TERMINAL_REQUEST_STATUSES:
        return False

    metadata = signature_request.provider_metadata_json or {}
    previous_at = _parse_iso(metadata.get('provider_state_at'))
    previous_rank = int(metadata.get('provider_state_rank') or 0)
    occurred_at = _callback_time(callback)
    incoming_rank = STATE_EVENT_RANK[event_type]

    if previous_at is None:
        return True

    return (incoming_rank, occurred_at) >= (
        previous_rank,
        previous_at,
    )


def _set_provider_state(signature_request, callback):
    event_type = callback.event_type

    if event_type not in STATE_EVENT_RANK:
        return

    occurred_at = _callback_time(callback)
    signature_request.provider_status = _provider_status(callback)
    signature_request.provider_metadata_json = {
        **(signature_request.provider_metadata_json or {}),
        'provider_state_at': occurred_at.isoformat(),
        'provider_state_rank': STATE_EVENT_RANK[event_type],
        'last_callback_event': event_type,
        'last_callback_at': occurred_at.isoformat(),
    }


def _record_workflow_event(
    signature_request,
    callback,
    *,
    recipient=None,
    state_applied=True,
):
    db.session.add(SignatureEvent(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        recipient_id=recipient.id if recipient else None,
        actor_user_id=None,
        event_type=f'provider.{callback.event_type}',
        description=(
            'Dropbox Sign provider event received: '
            f'{callback.event_type}'
        ),
        metadata_json={
            'provider': 'dropbox_sign',
            'provider_event_id': callback.event_id,
            'provider_request_id': callback.provider_request_id,
            'provider_recipient_id': (
                callback.provider_recipient_id
            ),
            'state_applied': state_applied,
        },
        occurred_at=_callback_time(callback),
    ))


def _notify_request_owner(signature_request, title, body):
    if not signature_request.created_by_id:
        return

    db.session.add(Notification(
        tenant_id=signature_request.tenant_id,
        user_id=signature_request.created_by_id,
        title=title,
        body=body,
        notification_type='signature',
    ))


def _disable_reminders(signature_request):
    if signature_request.reminder_rule:
        signature_request.reminder_rule.is_active = False
        signature_request.reminder_rule.next_run_at = None


def _mark_recipients_signed(signature_request, occurred_at):
    for recipient in signature_request.recipients:
        if recipient.status not in {
            'declined',
            'skipped',
            'expired',
        }:
            recipient.status = 'signed'
            recipient.signed_at = recipient.signed_at or occurred_at
            recipient.viewed_at = recipient.viewed_at or occurred_at
            recipient.provider_status = 'signed'


def _apply_callback(signature_request, callback):
    from app.services.signature_service import (
        refresh_document_signature_status,
    )

    event_type = callback.event_type
    occurred_at = _callback_time(callback)
    recipient = _recipient_for_callback(
        signature_request,
        callback,
    )
    state_applied = _can_apply_state(
        signature_request,
        callback,
    )

    if not state_applied:
        _record_workflow_event(
            signature_request,
            callback,
            recipient=recipient,
            state_applied=False,
        )
        return False

    _set_provider_state(signature_request, callback)

    if recipient and event_type in STATE_EVENT_RANK:
        recipient.provider_status = _provider_status(callback)
        recipient.provider_metadata_json = {
            **(recipient.provider_metadata_json or {}),
            'last_callback_event': event_type,
            'last_callback_at': occurred_at.isoformat(),
        }

    if event_type in {
        'signature_request_sent',
        'signature_request_prepared',
    }:
        if signature_request.status == 'draft':
            signature_request.status = 'sent'
        signature_request.sent_at = (
            signature_request.sent_at or occurred_at
        )

    elif event_type == 'signature_request_viewed':
        if recipient and recipient.status not in {
            'signed',
            'declined',
            'skipped',
            'expired',
        }:
            recipient.status = 'viewed'
            recipient.viewed_at = recipient.viewed_at or occurred_at

        if signature_request.status == 'sent':
            signature_request.status = 'in_progress'

    elif event_type == 'signature_request_signed':
        if recipient and recipient.status not in {
            'declined',
            'skipped',
            'expired',
        }:
            recipient.status = 'signed'
            recipient.signed_at = recipient.signed_at or occurred_at
            recipient.viewed_at = recipient.viewed_at or occurred_at

        if signature_request.status in {'sent', 'in_progress'}:
            signature_request.status = 'in_progress'

        _notify_request_owner(
            signature_request,
            f'Identity-verified signature received: '
            f'{signature_request.subject}',
            (
                'Dropbox Sign reported that the signer completed '
                'the eID signing ceremony. ACE is waiting for the '
                'final signed files and audit evidence.'
            ),
        )

    elif event_type == 'signature_request_all_signed':
        _mark_recipients_signed(signature_request, occurred_at)

        if signature_request.status in {'sent', 'in_progress'}:
            signature_request.status = 'in_progress'

        _disable_reminders(signature_request)

    elif event_type == 'signature_request_downloadable':
        _mark_recipients_signed(signature_request, occurred_at)
        signature_request.provider_downloadable_at = (
            signature_request.provider_downloadable_at
            or occurred_at
        )
        signature_request.provider_metadata_json = {
            **signature_request.provider_metadata_json,
            'evidence_pending': True,
            'assurance_confirmed': False,
        }

        if signature_request.status in {'sent', 'in_progress'}:
            signature_request.status = 'in_progress'

        _disable_reminders(signature_request)
        _notify_request_owner(
            signature_request,
            f'QES evidence ready: {signature_request.subject}',
            (
                'Dropbox Sign reported that the final signed files '
                'are downloadable. ACE must ingest and verify the '
                'signed PDF and audit evidence before completion.'
            ),
        )

    elif event_type == 'signature_request_declined':
        if recipient and recipient.status != 'signed':
            recipient.status = 'declined'
            recipient.declined_at = (
                recipient.declined_at or occurred_at
            )
            recipient.decline_reason = (
                recipient.decline_reason
                or _event_message(callback)
            )

        if signature_request.status != 'completed':
            signature_request.status = 'declined'

        _disable_reminders(signature_request)
        refresh_document_signature_status(
            signature_request.document,
        )
        _notify_request_owner(
            signature_request,
            f'Qualified-signature request declined: '
            f'{signature_request.subject}',
            _event_message(callback) or (
                'Dropbox Sign reported that the signer declined '
                'the provider-hosted request.'
            ),
        )

    elif event_type == 'signature_request_canceled':
        if signature_request.status != 'completed':
            signature_request.status = 'cancelled'
            signature_request.cancelled_at = (
                signature_request.cancelled_at or occurred_at
            )

        for item in signature_request.recipients:
            if item.status not in {
                'signed',
                'declined',
                'expired',
            }:
                item.status = 'skipped'

        _disable_reminders(signature_request)
        refresh_document_signature_status(
            signature_request.document,
        )
        _notify_request_owner(
            signature_request,
            f'Qualified-signature request cancelled: '
            f'{signature_request.subject}',
            'Dropbox Sign confirmed cancellation of the request.',
        )

    elif event_type == 'signature_request_expired':
        if signature_request.status != 'completed':
            signature_request.status = 'expired'

        for item in signature_request.recipients:
            if item.status not in {
                'signed',
                'declined',
                'skipped',
            }:
                item.status = 'expired'

        _disable_reminders(signature_request)
        refresh_document_signature_status(
            signature_request.document,
        )
        _notify_request_owner(
            signature_request,
            f'Qualified-signature request expired: '
            f'{signature_request.subject}',
            'Dropbox Sign reported that the request expired.',
        )

    elif event_type == 'signature_request_remind':
        if recipient:
            recipient.last_reminder_at = occurred_at

    elif event_type == 'signature_request_email_bounce':
        message = _event_message(callback)
        signature_request.provider_metadata_json = {
            **signature_request.provider_metadata_json,
            'provider_error': message,
        }

        if recipient:
            recipient.provider_status = 'email_bounce'

        _notify_request_owner(
            signature_request,
            f'QES invitation email failed: '
            f'{signature_request.subject}',
            message or (
                'Dropbox Sign reported that the signer email '
                'could not be delivered.'
            ),
        )

    elif event_type == 'signature_request_invalid':
        message = _event_message(callback)
        signature_request.status = 'failed'
        signature_request.provider_metadata_json = {
            **signature_request.provider_metadata_json,
            'provider_error': message,
        }
        _disable_reminders(signature_request)
        refresh_document_signature_status(
            signature_request.document,
        )
        _notify_request_owner(
            signature_request,
            f'QES request failed: {signature_request.subject}',
            message or (
                'Dropbox Sign reported that the request could not '
                'be processed.'
            ),
        )

    _record_workflow_event(
        signature_request,
        callback,
        recipient=recipient,
        state_applied=True,
    )
    return True


def _request_from_metadata(callback):
    payload_request = _payload_request(callback)
    metadata = payload_request.get('metadata') or {}
    request_id = metadata.get('ace_request_id')

    if not request_id:
        return None

    signature_request = db.session.get(
        SignatureRequest,
        request_id,
    )

    if not signature_request:
        return None

    if signature_request.provider not in {None, 'dropbox_sign'}:
        return None

    if (
        signature_request.provider_request_id
        and callback.provider_request_id
        and signature_request.provider_request_id
        != callback.provider_request_id
    ):
        return None

    expected_tenant = metadata.get('ace_tenant_id')

    if (
        expected_tenant
        and str(signature_request.tenant_id)
        != str(expected_tenant)
    ):
        return None

    signature_request.provider = 'dropbox_sign'

    if (
        callback.provider_request_id
        and not signature_request.provider_request_id
    ):
        signature_request.provider_request_id = (
            callback.provider_request_id
        )

    return signature_request


def record_dropbox_sign_callback(raw_payload):
    provider = get_signature_provider('dropbox_sign')
    callback = provider.parse_callback(raw_payload)

    existing = SignatureProviderEvent.query.filter_by(
        provider=provider.provider_name,
        provider_event_id=callback.event_id,
    ).first()

    if existing:
        return existing, False

    signature_request = None

    if callback.provider_request_id:
        signature_request = SignatureRequest.query.filter_by(
            provider=provider.provider_name,
            provider_request_id=callback.provider_request_id,
        ).first()

    if not signature_request:
        signature_request = _request_from_metadata(callback)

    event = SignatureProviderEvent(
        tenant_id=(
            signature_request.tenant_id
            if signature_request
            else None
        ),
        signature_request_id=(
            signature_request.id
            if signature_request
            else None
        ),
        provider=provider.provider_name,
        provider_event_id=callback.event_id,
        provider_request_id=callback.provider_request_id,
        event_type=callback.event_type,
        event_time=callback.event_time,
        payload_sha256=callback.payload_sha256,
        payload_json=callback.payload,
        signature_valid=True,
        processing_status=(
            'pending'
            if signature_request
            else 'unmatched'
        ),
    )
    db.session.add(event)

    if signature_request:
        event.processing_attempts = 1

        if callback.event_type in KNOWN_EVENTS:
            state_applied = _apply_callback(
                signature_request,
                callback,
            )
            event.processing_status = (
                'processed' if state_applied else 'ignored'
            )
        else:
            event.processing_status = 'ignored'

        event.processed_at = utcnow()

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()

        existing = SignatureProviderEvent.query.filter_by(
            provider=provider.provider_name,
            provider_event_id=callback.event_id,
        ).one()

        return existing, False

    return event, True
