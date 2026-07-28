from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import (
    SignatureProviderEvent,
    SignatureRequest,
)
from app.services.signature_providers.registry import (
    get_signature_provider,
)


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
