from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    SignatureArtifact,
    SignatureProviderEvent,
    SignatureRequest,
)
from app.utils.signature_evidence_storage import (
    save_signature_artifact,
    validate_signature_artifact_path,
)


def test_signature_provider_evidence_models(
    app,
    tenant,
    admin_user,
):
    admin_user_id = inspect(admin_user).identity[0]

    with app.app_context():
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Provider evidence contract',
            document_type='contract',
            original_filename='provider-contract.pdf',
            stored_filename='provider-contract-source.pdf',
            file_path='/tmp/provider-contract-source.pdf',
            mime_type='application/pdf',
            size_bytes=1024,
            checksum_sha256='a' * 64,
            signature_status='pending',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant.id,
            document_id=document.id,
            created_by_id=admin_user_id,
            subject='Provider-backed signature request',
            signing_mode='sequential',
            status='sent',
            due_at=datetime.utcnow() + timedelta(days=7),
            provider='dropbox_sign',
            provider_request_id='provider-request-123',
            provider_status='awaiting_signature',
            provider_test_mode=True,
            assurance_level='standard',
            provider_metadata_json={
                'source_checksum': document.checksum_sha256,
            },
        )
        db.session.add(signature_request)
        db.session.flush()

        artifact = SignatureArtifact(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            artifact_type='signed_document',
            provider='dropbox_sign',
            provider_artifact_id='artifact-123',
            original_filename='signed-provider-contract.pdf',
            stored_filename='signed-provider-contract-test.pdf',
            file_path='/tmp/signed-provider-contract-test.pdf',
            mime_type='application/pdf',
            size_bytes=2048,
            checksum_sha256='b' * 64,
            metadata_json={'download_event': 'downloadable'},
        )
        provider_event = SignatureProviderEvent(
            tenant_id=tenant.id,
            signature_request_id=signature_request.id,
            provider='dropbox_sign',
            provider_event_id='event-hash-123',
            provider_request_id='provider-request-123',
            event_type='signature_request_downloadable',
            event_time=datetime.utcnow(),
            payload_sha256='c' * 64,
            payload_json={'event': {'event_type': 'downloadable'}},
            signature_valid=True,
            processing_status='pending',
        )
        db.session.add_all([artifact, provider_event])
        db.session.commit()

        saved = db.session.get(
            SignatureRequest,
            signature_request.id,
        )

        assert saved.provider_status == 'awaiting_signature'
        assert saved.provider_test_mode is True
        assert saved.assurance_level == 'standard'
        assert len(saved.artifacts) == 1
        assert saved.artifacts[0].checksum_sha256 == 'b' * 64
        assert len(saved.provider_events) == 1
        assert saved.provider_events[0].signature_valid is True

        request_data = saved.to_dict()
        assert request_data['provider_status'] == (
            'awaiting_signature'
        )
        assert request_data['assurance_level'] == 'standard'

        artifact_data = saved.artifacts[0].to_dict()
        assert artifact_data['artifact_type'] == (
            'signed_document'
        )
        assert artifact_data['size_bytes'] == 2048

        event_data = saved.provider_events[0].to_dict()
        assert event_data['processing_status'] == 'pending'
        assert 'payload_json' not in event_data


def test_signature_artifact_storage_is_tenant_scoped(
    app,
    tenant,
    tmp_path,
):
    evidence_root = tmp_path / 'signature-evidence'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        evidence_root,
    )

    with app.app_context():
        stored = save_signature_artifact(
            b'%PDF-1.7 signed evidence',
            tenant_id=tenant.id,
            signature_request_id='request-123',
            filename='signed contract.pdf',
        )
        resolved = validate_signature_artifact_path(
            stored['file_path'],
        )

    assert resolved.exists()
    assert resolved.is_file()
    assert evidence_root.resolve() in resolved.parents
    assert str(tenant.id) in resolved.parts
    assert 'request-123' in resolved.parts
    assert stored['size_bytes'] == len(
        b'%PDF-1.7 signed evidence',
    )
    assert len(stored['checksum_sha256']) == 64
    assert Path(stored['file_path']).read_bytes() == (
        b'%PDF-1.7 signed evidence'
    )
