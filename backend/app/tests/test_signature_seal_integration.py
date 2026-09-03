import base64
import hashlib
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import inspect
from werkzeug.datastructures import FileStorage

from app.extensions import db
from app.models import (
    Document,
    Employee,
    SignatureArtifact,
    SignatureRequest,
    User,
)
from app.models.base import utcnow
from app.models.signature import SignatureEvent
from app.services.auth_service import register_user
from app.services.signature_seal_service import (
    SEAL_STATUS_APPLIED,
    SEAL_STATUS_PENDING,
    SignatureSealError,
    apply_signature_seal,
    initialize_seal_lifecycle,
    update_signature_seal_placement,
    upload_signature_seal_image,
)
from app.utils.signature_evidence_storage import (
    save_signature_artifact,
)


_TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'
    'CAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A'
    'AQUBAScY42YAAAAASUVORK5CYII='
)


def _make_pdf_bytes(page_count=2):
    output = BytesIO()
    pdf = canvas.Canvas(output)

    for page_number in range(1, page_count + 1):
        pdf.drawString(
            72,
            720,
            f'Executed agreement page {page_number}',
        )
        pdf.showPage()

    pdf.save()
    return output.getvalue()


def _image_xobject_count(page):
    resources = page.get('/Resources')

    if not resources:
        return 0

    xobjects = resources.get('/XObject')

    if not xobjects:
        return 0

    count = 0

    for reference in xobjects.values():
        obj = reference.get_object()

        if obj.get('/Subtype') == '/Image':
            count += 1

    return count


def _create_seal_required_request(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
    *,
    suffix,
):
    source_bytes = _make_pdf_bytes(page_count=2)
    source_path = tmp_path / f'source-{suffix}.pdf'
    source_path.write_bytes(source_bytes)

    with app.app_context():
        signer_user = register_user({
            'tenant_id': tenant.id,
            'email': f'seal-signer-{suffix}@acme.test',
            'first_name': 'Seal',
            'last_name': 'Signer',
            'password': 'StrongSealSignerPass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

        signer_user_id = inspect(
            signer_user
        ).identity[0]

        signer = Employee(
            tenant_id=tenant.id,
            user_id=signer_user_id,
            employee_number=f'SEAL-{suffix}',
            first_name='Seal',
            last_name='Signer',
            email=f'seal-signer-{suffix}@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(signer)
        db.session.flush()

        admin_user_id = inspect(
            admin_user
        ).identity[0]

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title=f'Seal Integration {suffix}',
            document_type='contract',
            original_filename=f'source-{suffix}.pdf',
            stored_filename=f'source-{suffix}.pdf',
            file_path=str(source_path),
            mime_type='application/pdf',
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(
                source_bytes
            ).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()

        employee_id = signer.id
        document_id = document.id

    due_at = (
        datetime.utcnow()
        + timedelta(days=7)
    ).replace(microsecond=0)

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': (
                f'Please sign seal integration {suffix}'
            ),
            'signing_mode': 'sequential',
            'assurance_level': 'standard',
            'seal_required': True,
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(employee_id),
                'role_label': 'Signatory',
                'sequence': 1,
            }],
        },
    )

    assert response.status_code == 201

    return response.get_json()['data']['id']


def _prepare_pending_seal(
    app,
    request_id,
    admin_user_id,
    *,
    page_number,
):
    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        actor = db.session.get(
            User,
            admin_user_id,
        )

        assert actor is not None

        signature_request.status = 'completed'
        signature_request.completed_at = utcnow()

        initialize_seal_lifecycle(
            signature_request
        )

        assert (
            signature_request.seal_status
            == SEAL_STATUS_PENDING
        )

        signed_bytes = _make_pdf_bytes(
            page_count=2
        )

        stored = save_signature_artifact(
            signed_bytes,
            tenant_id=signature_request.tenant_id,
            signature_request_id=signature_request.id,
            filename='agreement - Signed.pdf',
            mime_type='application/pdf',
        )

        signed_artifact = SignatureArtifact(
            tenant_id=signature_request.tenant_id,
            signature_request_id=signature_request.id,
            artifact_type='signed_document',
            provider='internal',
            original_filename=stored[
                'original_filename'
            ],
            stored_filename=stored[
                'stored_filename'
            ],
            file_path=stored['file_path'],
            mime_type='application/pdf',
            size_bytes=stored['size_bytes'],
            checksum_sha256=stored[
                'checksum_sha256'
            ],
            captured_at=utcnow(),
            metadata_json={
                'test_fixture': True,
            },
        )
        db.session.add(signed_artifact)
        db.session.flush()

        seal_file = FileStorage(
            stream=BytesIO(_TINY_PNG),
            filename='company-seal.png',
            content_type='image/png',
        )

        seal = upload_signature_seal_image(
            signature_request,
            seal_file,
            actor,
        )

        update_signature_seal_placement(
            signature_request,
            page_number=page_number,
            x=0.10,
            y=0.15,
            width=0.20,
            height=0.15,
        )

        db.session.commit()

        return {
            'signed_artifact_id': signed_artifact.id,
            'signed_checksum': signed_artifact.checksum_sha256,
            'signed_path': signed_artifact.file_path,
            'signed_bytes': signed_bytes,
            'seal_id': seal.id,
        }


def test_management_details_expose_pending_seal_metadata(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(
        tmp_path / 'uploads'
    )
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence'
    )

    admin_user_id = inspect(
        admin_user
    ).identity[0]

    request_id = _create_seal_required_request(
        client,
        app,
        tenant,
        admin_user,
        auth_headers,
        tmp_path,
        suffix='details',
    )

    prepared = _prepare_pending_seal(
        app,
        request_id,
        admin_user_id,
        page_number=2,
    )

    response = client.get(
        f'/api/signature-requests/{request_id}',
        headers=auth_headers,
    )

    assert response.status_code == 200

    payload = response.get_json()['data']

    assert payload['seal']['id'] == str(
        prepared['seal_id']
    )
    assert (
        payload['seal']['image_original_filename']
        == 'company-seal.png'
    )
    assert payload['seal']['page_number'] == 2
    assert payload['seal']['x'] == 0.10
    assert payload['seal']['y'] == 0.15
    assert payload['seal']['width'] == 0.20
    assert payload['seal']['height'] == 0.15

    assert (
        payload['signed_document']['id']
        == str(prepared['signed_artifact_id'])
    )


def test_management_can_download_persisted_company_seal_image(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(
        tmp_path / 'uploads'
    )
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence'
    )

    admin_user_id = inspect(
        admin_user
    ).identity[0]

    request_id = _create_seal_required_request(
        client,
        app,
        tenant,
        admin_user,
        auth_headers,
        tmp_path,
        suffix='image-download',
    )

    _prepare_pending_seal(
        app,
        request_id,
        admin_user_id,
        page_number=1,
    )

    response = client.get(
        f'/api/signature-requests/{request_id}/seal/image',
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.mimetype == 'image/png'
    assert response.data == _TINY_PNG


def test_management_seal_image_download_rejects_tampered_bytes(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(
        tmp_path / 'uploads'
    )
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence'
    )

    admin_user_id = inspect(
        admin_user
    ).identity[0]

    request_id = _create_seal_required_request(
        client,
        app,
        tenant,
        admin_user,
        auth_headers,
        tmp_path,
        suffix='image-tamper',
    )

    _prepare_pending_seal(
        app,
        request_id,
        admin_user_id,
        page_number=1,
    )

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        Path(
            signature_request.seal.image_file_path
        ).write_bytes(b'tampered-seal-image')

    response = client.get(
        f'/api/signature-requests/{request_id}/seal/image',
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert (
        response.get_json()['error']['code']
        == 'SIGNATURE_SEAL_IMAGE_FAILED'
    )


def test_apply_signature_seal_persists_complete_artifact_lineage(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(
        tmp_path / 'uploads'
    )
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence'
    )

    admin_user_id = inspect(
        admin_user
    ).identity[0]

    request_id = _create_seal_required_request(
        client,
        app,
        tenant,
        admin_user,
        auth_headers,
        tmp_path,
        suffix='success',
    )

    prepared = _prepare_pending_seal(
        app,
        request_id,
        admin_user_id,
        page_number=2,
    )

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        actor = db.session.get(
            User,
            admin_user_id,
        )

        assert actor is not None

        sealed_artifact = apply_signature_seal(
            signature_request,
            actor,
        )

        sealed_artifact_id = sealed_artifact.id

        db.session.commit()
        db.session.expire_all()

        persisted_request = db.session.get(
            SignatureRequest,
            request_id,
        )

        persisted_seal = persisted_request.seal

        persisted_signed = db.session.get(
            SignatureArtifact,
            prepared['signed_artifact_id'],
        )

        persisted_sealed = db.session.get(
            SignatureArtifact,
            sealed_artifact_id,
        )

        event = SignatureEvent.query.filter_by(
            signature_request_id=persisted_request.id,
            event_type='signature.company_seal_applied',
        ).one()

        assert (
            persisted_request.status
            == 'completed'
        )
        assert (
            persisted_request.seal_status
            == SEAL_STATUS_APPLIED
        )
        assert persisted_request.sealed_at is not None
        assert (
            persisted_request.sealed_by_id
            == admin_user_id
        )

        assert persisted_seal.applied_at is not None
        assert (
            persisted_seal.applied_by_id
            == admin_user_id
        )
        assert (
            persisted_seal.sealed_artifact_id
            == persisted_sealed.id
        )

        assert (
            persisted_sealed.artifact_type
            == 'sealed_document'
        )
        assert (
            persisted_sealed.checksum_sha256
            != persisted_signed.checksum_sha256
        )
        assert (
            len(persisted_sealed.checksum_sha256)
            == 64
        )

        metadata = (
            persisted_sealed.metadata_json
        )

        assert (
            metadata[
                'source_signed_document_artifact_id'
            ]
            == str(persisted_signed.id)
        )
        assert (
            metadata[
                'source_signed_document_sha256'
            ]
            == persisted_signed.checksum_sha256
        )
        assert (
            metadata['seal_image_sha256']
            == persisted_seal.image_sha256
        )
        assert metadata['seal_page_number'] == 2

        assert (
            event.metadata_json[
                'sealed_document_artifact_id'
            ]
            == str(persisted_sealed.id)
        )
        assert (
            event.metadata_json[
                'source_signed_document_artifact_id'
            ]
            == str(persisted_signed.id)
        )

        signed_path = Path(
            persisted_signed.file_path
        )
        sealed_path = Path(
            persisted_sealed.file_path
        )

        assert signed_path.read_bytes() == (
            prepared['signed_bytes']
        )
        assert (
            persisted_signed.checksum_sha256
            == prepared['signed_checksum']
        )

        assert sealed_path.exists()

        sealed_pdf = PdfReader(
            BytesIO(sealed_path.read_bytes())
        )

        assert len(sealed_pdf.pages) == 2
        assert (
            _image_xobject_count(
                sealed_pdf.pages[0]
            )
            == 0
        )
        assert (
            _image_xobject_count(
                sealed_pdf.pages[1]
            )
            >= 1
        )

        with pytest.raises(
            SignatureSealError
        ):
            apply_signature_seal(
                persisted_request,
                actor,
            )

        assert (
            SignatureArtifact.query.filter_by(
                signature_request_id=(
                    persisted_request.id
                ),
                artifact_type='sealed_document',
            ).count()
            == 1
        )

    details = client.get(
        f'/api/signature-requests/{request_id}',
        headers=auth_headers,
    )

    assert details.status_code == 200

    payload = details.get_json()['data']

    assert payload['sealed_document']['id'] == str(
        sealed_artifact_id
    )
    assert (
        payload['sealed_document']['artifact_type']
        == 'sealed_document'
   )


def test_failed_seal_render_leaves_request_pending(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['UPLOAD_FOLDER'] = str(
        tmp_path / 'uploads-failure'
    )
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence-failure'
    )

    admin_user_id = inspect(
        admin_user
    ).identity[0]

    request_id = _create_seal_required_request(
        client,
        app,
        tenant,
        admin_user,
        auth_headers,
        tmp_path,
        suffix='failure',
    )

    _prepare_pending_seal(
        app,
        request_id,
        admin_user_id,
        page_number=3,
    )

    with app.app_context():
        signature_request = db.session.get(
            SignatureRequest,
            request_id,
        )
        actor = db.session.get(
            User,
            admin_user_id,
        )

        assert actor is not None

        with pytest.raises(
            SignatureSealError
        ):
            apply_signature_seal(
                signature_request,
                actor,
            )

        db.session.rollback()
        db.session.expire_all()

        persisted_request = db.session.get(
            SignatureRequest,
            request_id,
        )

        assert (
            persisted_request.seal_status
            == SEAL_STATUS_PENDING
        )
        assert persisted_request.sealed_at is None
        assert persisted_request.sealed_by_id is None

        seal = persisted_request.seal

        assert seal.applied_at is None
        assert seal.applied_by_id is None
        assert seal.sealed_artifact_id is None

        assert (
            SignatureArtifact.query.filter_by(
                signature_request_id=(
                    persisted_request.id
                ),
                artifact_type='sealed_document',
            ).count()
            == 0
        )

        assert (
            SignatureEvent.query.filter_by(
                signature_request_id=(
                    persisted_request.id
                ),
                event_type=(
                    'signature.company_seal_applied'
                ),
            ).count()
            == 0
        )
