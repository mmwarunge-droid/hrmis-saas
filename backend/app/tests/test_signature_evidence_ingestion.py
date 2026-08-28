import hashlib

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Notification,
    SignatureArtifact,
    SignatureProviderEvent,
    SignatureRecipient,
    SignatureRequest,
    Tenant,
)
from app.models.base import utcnow
from app.services.auth_service import register_user
from app.services.signature_evidence_service import (
    claim_signature_evidence_jobs,
    process_signature_evidence,
)
from app.services.signature_providers.base import (
    ProviderArtifactPayload,
    SignatureArtifactsNotReady,
)


class FakeEvidenceProvider:
    def __init__(self, *, not_ready=False):
        self.not_ready = not_ready
        self.downloaded = []

    def download_artifacts(self, signature_request):
        self.downloaded.append(signature_request.id)

        if self.not_ready:
            raise SignatureArtifactsNotReady(
                'Provider files are still being prepared.',
            )

        return [
            ProviderArtifactPayload(
                artifact_type='signed_document',
                filename='signed-contract.pdf',
                content=b'%PDF-1.7 signed contract',
                mime_type='application/pdf',
            ),
            ProviderArtifactPayload(
                artifact_type='audit_trail',
                filename='Audit Trail.pdf',
                content=b'%PDF-1.7 audit trail',
                mime_type='application/pdf',
            ),
        ]


def _request_fixture(
    app,
    tenant,
    admin_user,
    tmp_path,
):
    source = tmp_path / 'source-contract.pdf'
    source.write_bytes(b'%PDF-1.7 source contract')
    source_checksum = hashlib.sha256(
        source.read_bytes(),
    ).hexdigest()
    admin_id = inspect(admin_user).identity[0]

    with app.app_context():
        app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
            tmp_path / 'signature-evidence',
        )
        app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
        app.config['SIGNATURE_EVIDENCE_RETRY_BASE_SECONDS'] = 1
        app.config['SIGNATURE_EVIDENCE_RETRY_MAX_SECONDS'] = 4
        app.config['SIGNATURE_EVIDENCE_MAX_ATTEMPTS'] = 3

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_id,
            title='Evidence contract',
            document_type='contract',
            original_filename='source-contract.pdf',
            stored_filename='source-contract.pdf',
            file_path=str(source),
            mime_type='application/pdf',
            size_bytes=source.stat().st_size,
            checksum_sha256=source_checksum,
            signature_status='pending',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document.id,
            created_by_id=admin_id,
            subject='Sign evidence contract',
            signing_mode='sequential',
            status='in_progress',
            current_sequence=1,
            provider='dropbox_sign',
            provider_request_id='provider-request-evidence',
            provider_status='downloadable',
            provider_test_mode=False,
            assurance_level='qes',
            provider_downloadable_at=utcnow(),
            evidence_status='pending',
            evidence_next_attempt_at=utcnow(),
        )
        db.session.add(signature_request)
        db.session.flush()

        recipient = SignatureRecipient(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            name='Evidence Signer',
            email='signer@example.test',
            role_label='Employee',
            sequence=1,
            status='signed',
            provider_recipient_id='provider-signer-evidence',
            provider_status='signed',
            signed_at=utcnow(),
        )
        db.session.add(recipient)

        event = SignatureProviderEvent(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            provider='dropbox_sign',
            provider_event_id='downloadable-event-1',
            provider_request_id='provider-request-evidence',
            event_type='signature_request_downloadable',
            event_time=utcnow(),
            payload_sha256='a' * 64,
            payload_json={
                'signature_request': {
                    'signature_request_id': (
                        'provider-request-evidence'
                    ),
                    'signatures': [{
                        'signature_id': (
                            'provider-signer-evidence'
                        ),
                        'signer_email_address': (
                            'signer@example.test'
                        ),
                    }],
                },
            },
            signature_valid=True,
            processing_status='processed',
            processing_attempts=1,
            processed_at=utcnow(),
        )
        db.session.add(event)
        db.session.commit()
        return str(signature_request.id), str(document.id)


def test_evidence_ingestion_completes_only_after_verification(
    app,
    tenant,
    admin_user,
    tmp_path,
    monkeypatch,
):
    request_id, document_id = _request_fixture(
        app,
        tenant,
        admin_user,
        tmp_path,
    )
    provider = FakeEvidenceProvider()
    monkeypatch.setattr(
        'app.services.signature_evidence_service.'
        'get_signature_provider',
        lambda _name: provider,
    )

    with app.app_context():
        claimed = claim_signature_evidence_jobs()
        assert claimed == [request_id]

        result = process_signature_evidence(request_id)

        assert result.status == 'completed'
        assert result.evidence_status == 'verified'
        assert result.evidence_completed_at is not None
        assert result.evidence_verification_json[
            'legal_assurance_confirmed'
        ] is False
        assert result.document.signature_status == 'signed'
        assert {
            artifact.artifact_type
            for artifact in SignatureArtifact.query.filter_by(
                signature_request_id=request_id,
            ).all()
        } == {
            'signed_document',
            'audit_trail',
        }
        assert len(provider.downloaded) == 1
        assert db.session.get(
            Document,
            document_id,
        ).signature_status == 'signed'


def test_evidence_ingestion_schedules_provider_409_retry(
    app,
    tenant,
    admin_user,
    tmp_path,
    monkeypatch,
):
    request_id, _document_id = _request_fixture(
        app,
        tenant,
        admin_user,
        tmp_path,
    )
    provider = FakeEvidenceProvider(not_ready=True)
    monkeypatch.setattr(
        'app.services.signature_evidence_service.'
        'get_signature_provider',
        lambda _name: provider,
    )

    with app.app_context():
        assert claim_signature_evidence_jobs() == [request_id]

        result = process_signature_evidence(request_id)

        assert result.status == 'in_progress'
        assert result.evidence_status == 'retry_scheduled'
        assert result.evidence_attempts == 1
        assert result.evidence_next_attempt_at is not None
        assert 'still being prepared' in (
            result.evidence_last_error
        )


def test_evidence_verification_does_not_notify_cross_tenant_request_creator(
    app,
    tenant,
    admin_user,
    tmp_path,
    monkeypatch,
):
    """Malformed created_by_id must not create a cross-tenant notification."""
    request_id, _document_id = _request_fixture(
        app,
        tenant,
        admin_user,
        tmp_path,
    )

    provider = FakeEvidenceProvider()
    monkeypatch.setattr(
        'app.services.signature_evidence_service.'
        'get_signature_provider',
        lambda _name: provider,
    )

    with app.app_context():
        foreign_tenant = Tenant(
            name='Foreign Evidence Owner Tenant',
            slug='foreign-evidence-owner-tenant',
            country='Kenya',
        )
        db.session.add(foreign_tenant)
        db.session.flush()

        foreign_user = register_user({
            'tenant_id': foreign_tenant.id,
            'email': 'foreign.evidence.owner@other.test',
            'first_name': 'Foreign',
            'last_name': 'EvidenceOwner',
            'password': 'StrongForeignEvidencePass123!',
            'roles': ['CLIENT_ADMIN'],
            'email_verified_at': utcnow(),
        })
        foreign_user_id = inspect(foreign_user).identity[0]

        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        signature_request.created_by_id = foreign_user_id
        db.session.commit()

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0

        claimed = claim_signature_evidence_jobs()
        assert claimed == [request_id]

        result = process_signature_evidence(request_id)

        assert result.status == 'completed'
        assert result.evidence_status == 'verified'

        assert Notification.query.filter_by(
            tenant_id=tenant.id,
            user_id=foreign_user_id,
            notification_type='signature',
        ).count() == 0