import hashlib
import logging
from datetime import timedelta
from pathlib import Path

from flask import current_app
from sqlalchemy import or_

from app.extensions import db
from app.models import (
    Notification,
    SignatureArtifact,
    SignatureEvent,
    SignatureProviderEvent,
    SignatureRequest,
)
from app.models.base import utcnow
from app.services.signature_providers.base import (
    SignatureArtifactsNotReady,
    SignatureProviderError,
    SignatureProviderRetryableError,
)
from app.services.signature_providers.registry import (
    get_signature_provider,
)
from app.utils.signature_evidence_storage import (
    delete_signature_artifact,
    read_signature_artifact,
    save_signature_artifact,
)


logger = logging.getLogger(__name__)

REQUIRED_PROVIDER_ARTIFACTS = {
    'signed_document',
    'audit_trail',
}
RETRYABLE_EVIDENCE_STATUSES = {
    'pending',
    'retry_scheduled',
}
MANUAL_RETRY_STATUSES = {
    'failed',
    'retry_scheduled',
}


class SignatureEvidenceError(RuntimeError):
    pass


class SignatureEvidenceValidationError(
    SignatureEvidenceError,
    ValueError,
):
    pass


def _record_event(
    signature_request,
    event_type,
    description,
    *,
    actor_user_id=None,
    metadata=None,
):
    event = SignatureEvent(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        description=description,
        metadata_json=metadata or {},
        occurred_at=utcnow(),
    )
    db.session.add(event)
    return event


def _notify_owner(signature_request, title, body):
    if not signature_request.created_by_id:
        return

    db.session.add(Notification(
        tenant_id=signature_request.tenant_id,
        user_id=signature_request.created_by_id,
        title=title,
        body=body,
        notification_type='signature',
    ))


def _expected_source_checksum(signature_request):
    checksum = (
        signature_request.document.checksum_sha256 or ''
    ).lower()

    if len(checksum) != 64:
        raise SignatureEvidenceValidationError(
            'The source document SHA-256 checksum is missing.',
        )

    return checksum


def capture_source_artifact(signature_request):
    existing = SignatureArtifact.query.filter_by(
        signature_request_id=signature_request.id,
        artifact_type='original_document',
    ).first()

    if existing:
        return existing

    document = signature_request.document
    source_path = Path(document.file_path)

    if not source_path.is_file():
        if current_app.config.get('TESTING'):
            return None
        raise SignatureEvidenceValidationError(
            'The source document is unavailable for evidence '
            'capture.',
        )

    content = source_path.read_bytes()
    checksum = hashlib.sha256(content).hexdigest()
    expected = _expected_source_checksum(signature_request)

    if checksum != expected:
        raise SignatureEvidenceValidationError(
            'The source document checksum no longer matches '
            'the uploaded document record.',
        )

    stored = save_signature_artifact(
        content,
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        filename=document.original_filename,
        mime_type=document.mime_type or 'application/pdf',
    )
    artifact = SignatureArtifact(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type='original_document',
        provider='ace',
        original_filename=stored['original_filename'],
        stored_filename=stored['stored_filename'],
        file_path=stored['file_path'],
        mime_type=document.mime_type or 'application/pdf',
        size_bytes=stored['size_bytes'],
        checksum_sha256=stored['checksum_sha256'],
        metadata_json={
            'document_id': str(document.id),
            'capture_stage': 'before_provider_submission',
        },
    )
    db.session.add(artifact)
    db.session.flush()
    return artifact


def queue_signature_evidence(
    signature_request,
    *,
    available_at=None,
):
    if (
        signature_request.provider != 'dropbox_sign'
        or signature_request.assurance_level != 'qes'
    ):
        return False

    if signature_request.evidence_status == 'verified':
        return False

    now = available_at or utcnow()
    signature_request.evidence_status = 'pending'
    signature_request.evidence_next_attempt_at = now
    signature_request.evidence_locked_at = None
    signature_request.evidence_last_error = None
    signature_request.provider_metadata_json = {
        **(signature_request.provider_metadata_json or {}),
        'evidence_pending': True,
        'evidence_verified': False,
        'assurance_confirmed': False,
    }
    return True


def claim_signature_evidence_jobs(limit=None):
    now = utcnow()
    lock_timeout = int(current_app.config.get(
        'SIGNATURE_EVIDENCE_LOCK_TIMEOUT_SECONDS',
        900,
    ))
    stale_before = now - timedelta(seconds=lock_timeout)
    batch_size = limit or int(current_app.config.get(
        'SIGNATURE_EVIDENCE_WORKER_BATCH_SIZE',
        10,
    ))

    rows = (
        SignatureRequest.query
        .filter(
            SignatureRequest.provider == 'dropbox_sign',
            SignatureRequest.assurance_level == 'qes',
            SignatureRequest.provider_downloadable_at.isnot(None),
            or_(
                SignatureRequest.evidence_status.in_(
                    RETRYABLE_EVIDENCE_STATUSES,
                ),
                (
                    (SignatureRequest.evidence_status == 'processing')
                    & or_(
                        SignatureRequest.evidence_locked_at.is_(None),
                        SignatureRequest.evidence_locked_at
                        < stale_before,
                    )
                ),
            ),
            or_(
                SignatureRequest.evidence_next_attempt_at.is_(None),
                SignatureRequest.evidence_next_attempt_at <= now,
            ),
        )
        .order_by(
            SignatureRequest.evidence_next_attempt_at.asc(),
            SignatureRequest.provider_downloadable_at.asc(),
        )
        .with_for_update(skip_locked=True)
        .limit(batch_size)
        .all()
    )

    claimed_ids = []

    for signature_request in rows:
        signature_request.evidence_status = 'processing'
        signature_request.evidence_attempts += 1
        signature_request.evidence_last_attempt_at = now
        signature_request.evidence_locked_at = now
        signature_request.evidence_next_attempt_at = None
        signature_request.evidence_last_error = None
        claimed_ids.append(str(signature_request.id))

    db.session.commit()
    return claimed_ids


def _downloadable_event(signature_request):
    event = (
        SignatureProviderEvent.query
        .filter_by(
            signature_request_id=signature_request.id,
            provider='dropbox_sign',
            event_type='signature_request_downloadable',
            signature_valid=True,
        )
        .order_by(SignatureProviderEvent.received_at.desc())
        .first()
    )

    if not event:
        raise SignatureEvidenceValidationError(
            'No verified downloadable callback exists for '
            'this signature request.',
        )

    if event.processing_status not in {'processed', 'ignored'}:
        raise SignatureEvidenceValidationError(
            'The downloadable callback has not been processed.',
        )

    return event


def _validate_provider_identity(signature_request, event):
    payload_request = (
        event.payload_json.get('signature_request') or {}
    )

    if (
        payload_request.get('signature_request_id')
        != signature_request.provider_request_id
    ):
        raise SignatureEvidenceValidationError(
            'The evidence callback request ID does not match.',
        )

    signatures = payload_request.get('signatures') or []

    if len(signatures) != 1 or len(
        signature_request.recipients,
    ) != 1:
        raise SignatureEvidenceValidationError(
            'QES evidence must resolve to exactly one signer.',
        )

    expected = signature_request.recipients[0]
    actual = signatures[0]
    actual_email = (
        actual.get('signer_email_address') or ''
    ).lower()
    actual_id = actual.get('signature_id')

    if actual_email != expected.email.lower():
        raise SignatureEvidenceValidationError(
            'The evidence signer email does not match the '
            'assigned employee.',
        )

    if (
        expected.provider_recipient_id
        and actual_id != expected.provider_recipient_id
    ):
        raise SignatureEvidenceValidationError(
            'The evidence signer ID does not match the '
            'provider recipient.',
        )

    return {
        'provider_event_id': event.provider_event_id,
        'provider_event_sha256': event.payload_sha256,
        'provider_recipient_id': actual_id,
        'signer_email': actual_email,
    }


def _validate_provider_artifacts(artifacts):
    artifact_map = {}

    for artifact in artifacts:
        if artifact.artifact_type in artifact_map:
            raise SignatureEvidenceValidationError(
                'The provider returned a duplicate evidence '
                'artifact type.',
            )
        artifact_map[artifact.artifact_type] = artifact

    if set(artifact_map) != REQUIRED_PROVIDER_ARTIFACTS:
        raise SignatureEvidenceValidationError(
            'The provider evidence package must contain the '
            'signed PDF and audit trail.',
        )

    for artifact in artifact_map.values():
        if not artifact.content.startswith(b'%PDF-'):
            raise SignatureEvidenceValidationError(
                'A provider evidence artifact is not a valid PDF.',
            )

    return artifact_map


def _persist_provider_artifact(
    signature_request,
    payload,
):
    checksum = hashlib.sha256(payload.content).hexdigest()
    existing = SignatureArtifact.query.filter_by(
        signature_request_id=signature_request.id,
        artifact_type=payload.artifact_type,
    ).first()

    if existing:
        if existing.checksum_sha256 != checksum:
            raise SignatureEvidenceValidationError(
                'A stored evidence artifact conflicts with the '
                'provider package.',
            )
        return existing, None

    stored = save_signature_artifact(
        payload.content,
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        filename=payload.filename,
        mime_type=payload.mime_type,
    )
    artifact = SignatureArtifact(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type=payload.artifact_type,
        provider=signature_request.provider,
        provider_artifact_id=payload.provider_artifact_id,
        original_filename=stored['original_filename'],
        stored_filename=stored['stored_filename'],
        file_path=stored['file_path'],
        mime_type=payload.mime_type,
        size_bytes=stored['size_bytes'],
        checksum_sha256=stored['checksum_sha256'],
        metadata_json=payload.metadata,
    )
    db.session.add(artifact)
    db.session.flush()
    return artifact, stored['file_path']


def _retry_delay(attempts):
    base = int(current_app.config.get(
        'SIGNATURE_EVIDENCE_RETRY_BASE_SECONDS',
        30,
    ))
    maximum = int(current_app.config.get(
        'SIGNATURE_EVIDENCE_RETRY_MAX_SECONDS',
        1800,
    ))
    exponent = max(0, attempts - 1)
    return min(maximum, base * (2 ** exponent))


def _schedule_retry(signature_request, error):
    now = utcnow()
    maximum = int(current_app.config.get(
        'SIGNATURE_EVIDENCE_MAX_ATTEMPTS',
        8,
    ))
    signature_request.evidence_locked_at = None
    signature_request.evidence_last_error = str(error)

    if signature_request.evidence_attempts >= maximum:
        signature_request.evidence_status = 'failed'
        signature_request.evidence_next_attempt_at = None
        _record_event(
            signature_request,
            'signature.evidence_failed',
            'QES evidence ingestion exhausted all retries',
            metadata={
                'attempts': signature_request.evidence_attempts,
                'error': str(error),
            },
        )
        _notify_owner(
            signature_request,
            f'QES evidence ingestion failed: '
            f'{signature_request.subject}',
            (
                'Kinetic could not retrieve and verify the final '
                'Dropbox Sign evidence package. An administrator '
                'can retry the evidence job after reviewing the '
                'provider status.'
            ),
        )
    else:
        delay = _retry_delay(
            signature_request.evidence_attempts,
        )
        signature_request.evidence_status = 'retry_scheduled'
        signature_request.evidence_next_attempt_at = (
            now + timedelta(seconds=delay)
        )
        _record_event(
            signature_request,
            'signature.evidence_retry_scheduled',
            'QES evidence ingestion will be retried',
            metadata={
                'attempts': signature_request.evidence_attempts,
                'delay_seconds': delay,
                'error': str(error),
            },
        )


def _mark_permanent_failure(signature_request, error):
    signature_request.evidence_status = 'failed'
    signature_request.evidence_next_attempt_at = None
    signature_request.evidence_locked_at = None
    signature_request.evidence_last_error = str(error)
    _record_event(
        signature_request,
        'signature.evidence_failed',
        'QES evidence verification failed',
        metadata={
            'attempts': signature_request.evidence_attempts,
            'error': str(error),
        },
    )
    _notify_owner(
        signature_request,
        f'QES evidence verification failed: '
        f'{signature_request.subject}',
        (
            'Kinetic retrieved the provider package but could not '
            'verify its request, signer, or artifact consistency. '
            'The request remains incomplete pending review.'
        ),
    )


def process_signature_evidence(request_id):
    signature_request = db.session.get(
        SignatureRequest,
        request_id,
    )

    if not signature_request:
        raise SignatureEvidenceError(
            'Signature request does not exist.',
        )

    if signature_request.evidence_status == 'verified':
        return signature_request

    if signature_request.evidence_status != 'processing':
        raise SignatureEvidenceError(
            'Signature evidence job has not been claimed.',
        )

    created_paths = []

    try:
        event = _downloadable_event(signature_request)
        identity = _validate_provider_identity(
            signature_request,
            event,
        )
        source_checksum = _expected_source_checksum(
            signature_request,
        )
        provider = get_signature_provider(
            signature_request.provider,
        )
        payloads = provider.download_artifacts(
            signature_request,
        )
        artifact_map = _validate_provider_artifacts(payloads)
        persisted = {}

        for artifact_type in sorted(artifact_map):
            artifact, created_path = _persist_provider_artifact(
                signature_request,
                artifact_map[artifact_type],
            )
            persisted[artifact_type] = artifact

            if created_path:
                created_paths.append(created_path)

        verification = {
            'verification_scope': (
                'provider_package_integrity_and_mapping'
            ),
            'provider': signature_request.provider,
            'provider_request_id': (
                signature_request.provider_request_id
            ),
            'source_document_sha256': source_checksum,
            'signed_document_sha256': persisted[
                'signed_document'
            ].checksum_sha256,
            'audit_trail_sha256': persisted[
                'audit_trail'
            ].checksum_sha256,
            'downloadable_callback': identity,
            'verified_at': utcnow().isoformat(),
            'legal_assurance_confirmed': False,
        }

        signature_request.evidence_status = 'verified'
        signature_request.evidence_completed_at = utcnow()
        signature_request.evidence_next_attempt_at = None
        signature_request.evidence_locked_at = None
        signature_request.evidence_last_error = None
        signature_request.evidence_verification_json = (
            verification
        )
        signature_request.provider_metadata_json = {
            **(signature_request.provider_metadata_json or {}),
            'evidence_pending': False,
            'evidence_verified': True,
            'assurance_confirmed': False,
            'verification_scope': verification[
                'verification_scope'
            ],
        }
        signature_request.status = 'completed'
        signature_request.completed_at = (
            signature_request.completed_at or utcnow()
        )

        from app.services.signature_service import (
            refresh_document_signature_status,
        )

        refresh_document_signature_status(
            signature_request.document,
        )
        _record_event(
            signature_request,
            'signature.evidence_verified',
            'Signed PDF and audit evidence ingested and verified',
            metadata=verification,
        )
        _notify_owner(
            signature_request,
            f'QES evidence verified: '
            f'{signature_request.subject}',
            (
                'Kinetic retrieved the final signed PDF and provider '
                'audit trail, verified their integrity and request '
                'mapping, and completed the workflow.'
            ),
        )
        db.session.commit()
        return signature_request
    except (
        SignatureArtifactsNotReady,
        SignatureProviderRetryableError,
    ) as exc:
        db.session.rollback()
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        _schedule_retry(signature_request, exc)
        db.session.commit()
        return signature_request
    except (
        SignatureEvidenceValidationError,
        SignatureProviderError,
    ) as exc:
        db.session.rollback()

        for file_path in created_paths:
            try:
                delete_signature_artifact(file_path)
            except Exception:
                logger.exception(
                    'Could not delete uncommitted evidence artifact',
                )

        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        _mark_permanent_failure(signature_request, exc)
        db.session.commit()
        return signature_request
    except Exception as exc:
        logger.exception(
            'Unexpected signature evidence ingestion failure',
        )
        db.session.rollback()

        for file_path in created_paths:
            try:
                delete_signature_artifact(file_path)
            except Exception:
                logger.exception(
                    'Could not delete uncommitted evidence artifact',
                )

        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        _schedule_retry(signature_request, exc)
        db.session.commit()
        return signature_request


def retry_signature_evidence(
    signature_request,
    actor,
):
    if (
        signature_request.provider != 'dropbox_sign'
        or signature_request.assurance_level != 'qes'
    ):
        raise ValueError(
            'Evidence retry is only available for Dropbox Sign '
            'QES requests.',
        )

    if signature_request.evidence_status not in (
        MANUAL_RETRY_STATUSES
    ):
        raise ValueError(
            'This evidence job is not eligible for manual retry.',
        )

    signature_request.evidence_status = 'pending'
    signature_request.evidence_attempts = 0
    signature_request.evidence_next_attempt_at = utcnow()
    signature_request.evidence_last_attempt_at = None
    signature_request.evidence_locked_at = None
    signature_request.evidence_last_error = None
    _record_event(
        signature_request,
        'signature.evidence_retry_requested',
        'An administrator requested a QES evidence retry',
        actor_user_id=actor.id,
    )
    db.session.commit()
    return signature_request


def serialize_signature_evidence(signature_request):
    return {
        'request_id': str(signature_request.id),
        'provider': signature_request.provider,
        'assurance_level': signature_request.assurance_level,
        'evidence_status': signature_request.evidence_status,
        'evidence_attempts': signature_request.evidence_attempts,
        'evidence_next_attempt_at': (
            signature_request.evidence_next_attempt_at.isoformat()
            if signature_request.evidence_next_attempt_at
            else None
        ),
        'evidence_last_attempt_at': (
            signature_request.evidence_last_attempt_at.isoformat()
            if signature_request.evidence_last_attempt_at
            else None
        ),
        'evidence_completed_at': (
            signature_request.evidence_completed_at.isoformat()
            if signature_request.evidence_completed_at
            else None
        ),
        'evidence_last_error': (
            signature_request.evidence_last_error
        ),
        'verification': (
            signature_request.evidence_verification_json or {}
        ),
        'artifacts': [
            artifact.to_dict()
            for artifact in signature_request.artifacts
        ],
    }


def artifact_content(artifact):
    content = read_signature_artifact(artifact.file_path)
    checksum = hashlib.sha256(content).hexdigest()

    if checksum != artifact.checksum_sha256:
        raise SignatureEvidenceValidationError(
            'Stored evidence artifact checksum verification failed.',
        )

    return content
