import hashlib

import pytest
from datetime import datetime, timedelta
from io import BytesIO

from pypdf import PdfReader
from reportlab.pdfgen import canvas
from sqlalchemy import inspect

from app.extensions import db
from app.models import (
    Document,
    Employee,
    SignatureArtifact,
    SignatureField,
    SignatureRecipient,
    SignatureRequest,
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
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    return _csrf_header(client)


def _make_pdf(path):
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 760, 'Independent Contractor Agreement')
    pdf.drawString(72, 720, 'Please review this agreement before signing.')
    pdf.save()
    return path.read_bytes()


def test_native_signing_generates_identity_fields_and_final_pdf(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence',
    )

    source_path = tmp_path / 'contract.pdf'
    source_bytes = _make_pdf(source_path)

    with app.app_context():
        signer_user = register_user({
            'tenant_id': tenant.id,
            'email': 'mark.warunge@acme.test',
            'first_name': 'Mark',
            'last_name': 'Warunge',
            'password': 'StrongSignerPass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        signer_user_id = inspect(signer_user).identity[0]
        signer = Employee(
            tenant_id=tenant.id,
            user_id=signer_user_id,
            employee_number='SIGN-NATIVE-001',
            first_name='Mark',
            last_name='Warunge',
            email='mark.warunge@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(signer)
        db.session.flush()

        admin_user_id = inspect(admin_user).identity[0]
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Independent Contractor Agreement',
            document_type='contract',
            original_filename='contract.pdf',
            stored_filename='contract.pdf',
            file_path=str(source_path),
            mime_type='application/pdf',
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(source_bytes).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()
        employee_id = signer.id
        document_id = document.id

    due_at = (datetime.utcnow() + timedelta(days=7)).replace(
        microsecond=0,
    )
    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Please sign: Independent Contractor Agreement',
            'signing_mode': 'sequential',
            'assurance_level': 'standard',
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(employee_id),
                'role_label': 'Contractor',
                'sequence': 1,
            }],
        },
    )
    assert create_response.status_code == 201

    created = create_response.get_json()['data']
    recipient_id = created['recipients'][0]['id']
    assert len(created['fields']) == 2
    assert {field['field_type'] for field in created['fields']} == {
        'signature',
        'date',
    }
    assert {field['page_number'] for field in created['fields']} == {2}

    employee_headers = _login(
        client,
        'mark.warunge@acme.test',
        'StrongSignerPass123!',
    )

    details_response = client.get(
        f'/api/signature-requests/recipients/{recipient_id}',
    )
    assert details_response.status_code == 200
    details = details_response.get_json()['data']
    assert details['signature_preview'] == 'M.Warunge'

    preview_response = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/document',
    )
    assert preview_response.status_code == 200
    preview_pdf = PdfReader(BytesIO(preview_response.data))
    assert len(preview_pdf.pages) == 2

    viewed_response = client.patch(
        f'/api/signature-requests/recipients/{recipient_id}/viewed',
        headers=employee_headers,
    )
    assert viewed_response.status_code == 200

    submit_response = client.post(
        f'/api/signature-requests/recipients/{recipient_id}/submit',
        headers=employee_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_1',
        },
    )
    assert submit_response.status_code == 200

    with app.app_context():
        recipient = db.session.get(SignatureRecipient, recipient_id)
        signature_request = db.session.get(
            SignatureRequest,
            created['id'],
        )
        fields = SignatureField.query.filter_by(
            recipient_id=recipient.id,
        ).all()
        artifact = SignatureArtifact.query.filter_by(
            signature_request_id=signature_request.id,
            artifact_type='signed_document',
        ).one()

        assert recipient.signature_name == 'M.Warunge'
        assert recipient.signature_method == 'generated_typed'
        assert recipient.consented_at is not None
        assert recipient.signed_at is not None
        assert signature_request.status == 'completed'
        assert all(field.completed_at is not None for field in fields)
        assert {field.field_type: field.value for field in fields}[
            'signature'
        ] == 'M.Warunge'
        assert len(artifact.checksum_sha256) == 64

    signed_response = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/signed-document',
    )
    assert signed_response.status_code == 200
    signed_pdf = PdfReader(BytesIO(signed_response.data))
    assert len(signed_pdf.pages) == 2
    signing_record_text = signed_pdf.pages[-1].extract_text()
    assert 'Kinetic Electronic Signing Record' in signing_record_text
    assert 'M.Warunge' in signing_record_text


def test_parallel_signers_fill_only_their_assigned_pdf_fields(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence-parallel',
    )

    source_path = tmp_path / 'parallel-contract.pdf'
    source_bytes = _make_pdf(source_path)

    signer_specs = [
        (
            'mark.parallel@acme.test',
            'Mark',
            'Warunge',
            'SIGN-NATIVE-101',
            'ParallelMarkPass123!',
        ),
        (
            'jane.parallel@acme.test',
            'Jane',
            'Doe',
            'SIGN-NATIVE-102',
            'ParallelJanePass123!',
        ),
    ]

    with app.app_context():
        employees = []
        for email, first_name, last_name, number, password in signer_specs:
            signer_user = register_user({
                'tenant_id': tenant.id,
                'email': email,
                'first_name': first_name,
                'last_name': last_name,
                'password': password,
                'roles': ['EMPLOYEE'],
                'email_verified_at': utcnow(),
            })
            signer_user_id = inspect(signer_user).identity[0]
            employee = Employee(
                tenant_id=tenant.id,
                user_id=signer_user_id,
                employee_number=number,
                first_name=first_name,
                last_name=last_name,
                email=email,
                hire_date=datetime.utcnow().date(),
                employment_status='active',
                employment_type='full_time',
            )
            db.session.add(employee)
            employees.append(employee)

        db.session.flush()
        admin_user_id = inspect(admin_user).identity[0]
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Parallel Independent Contractor Agreement',
            document_type='contract',
            original_filename='parallel-contract.pdf',
            stored_filename='parallel-contract.pdf',
            file_path=str(source_path),
            mime_type='application/pdf',
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(source_bytes).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()
        employee_ids = [employee.id for employee in employees]
        document_id = document.id

    due_at = (datetime.utcnow() + timedelta(days=7)).replace(
        microsecond=0,
    )
    recipient_payloads = [
        {
            'employee_id': str(employee_ids[0]),
            'role_label': 'Contractor',
            'sequence': 1,
            'fields': [
                {
                    'field_type': 'signature',
                    'page_number': 1,
                    'x': 0.08,
                    'y': 0.70,
                    'width': 0.30,
                    'height': 0.07,
                },
                {
                    'field_type': 'date',
                    'page_number': 1,
                    'x': 0.08,
                    'y': 0.80,
                    'width': 0.19,
                    'height': 0.05,
                },
            ],
        },
        {
            'employee_id': str(employee_ids[1]),
            'role_label': 'HR representative',
            'sequence': 1,
            'fields': [
                {
                    'field_type': 'signature',
                    'page_number': 1,
                    'x': 0.55,
                    'y': 0.70,
                    'width': 0.30,
                    'height': 0.07,
                },
                {
                    'field_type': 'date',
                    'page_number': 1,
                    'x': 0.55,
                    'y': 0.80,
                    'width': 0.19,
                    'height': 0.05,
                },
            ],
        },
    ]

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Please sign: Parallel Agreement',
            'signing_mode': 'parallel',
            'assurance_level': 'standard',
            'due_at': due_at.isoformat(),
            'recipients': recipient_payloads,
        },
    )
    assert create_response.status_code == 201
    created = create_response.get_json()['data']
    assert len(created['fields']) == 4
    assert {field['page_number'] for field in created['fields']} == {1}

    recipients_by_name = {
        item['name']: item
        for item in created['recipients']
    }
    mark_id = recipients_by_name['Mark Warunge']['id']
    jane_id = recipients_by_name['Jane Doe']['id']

    mark_fields = {
        field['field_type']: field
        for field in created['fields']
        if field['recipient_id'] == mark_id
    }
    jane_fields = {
        field['field_type']: field
        for field in created['fields']
        if field['recipient_id'] == jane_id
    }
    assert mark_fields['signature']['x'] == 0.08
    assert jane_fields['signature']['x'] == 0.55

    mark_headers = _login(
        client,
        'mark.parallel@acme.test',
        'ParallelMarkPass123!',
    )
    client.patch(
        f'/api/signature-requests/recipients/{mark_id}/viewed',
        headers=mark_headers,
    )
    mark_submit = client.post(
        f'/api/signature-requests/recipients/{mark_id}/submit',
        headers=mark_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_1',
        },
    )
    assert mark_submit.status_code == 200
    assert mark_submit.get_json()['data']['status'] == 'signed'

    with app.app_context():
        request_after_mark = db.session.get(
            SignatureRequest,
            created['id'],
        )
        assert request_after_mark.status == 'in_progress'

    jane_headers = _login(
        client,
        'jane.parallel@acme.test',
        'ParallelJanePass123!',
    )
    client.patch(
        f'/api/signature-requests/recipients/{jane_id}/viewed',
        headers=jane_headers,
    )
    jane_submit = client.post(
        f'/api/signature-requests/recipients/{jane_id}/submit',
        headers=jane_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_2',
        },
    )
    assert jane_submit.status_code == 200
    assert jane_submit.get_json()['data']['status'] == 'signed'

    with app.app_context():
        completed_request = db.session.get(
            SignatureRequest,
            created['id'],
        )
        assert completed_request.status == 'completed'

    signed_response = client.get(
        f'/api/signature-requests/recipients/{jane_id}/signed-document',
    )
    assert signed_response.status_code == 200
    signed_pdf = PdfReader(BytesIO(signed_response.data))
    assert len(signed_pdf.pages) == 1
    page_text = signed_pdf.pages[0].extract_text()
    assert 'M.Warunge' in page_text
    assert 'J.Doe' in page_text

    with app.app_context():
        mark = db.session.get(SignatureRecipient, mark_id)
        jane = db.session.get(SignatureRecipient, jane_id)
        mark_values = {
            field.field_type: field.value
            for field in mark.fields
        }
        jane_values = {
            field.field_type: field.value
            for field in jane.fields
        }
        assert mark_values['signature'] == 'M.Warunge'
        assert jane_values['signature'] == 'J.Doe'
        assert mark_values['date']
        assert jane_values['date']


def test_standard_docx_signing_uses_immutable_converted_pdf_snapshot(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    from app.services.document_conversion_service import ConvertedPdf

    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence-docx',
    )

    source_path = tmp_path / 'employment-agreement.docx'
    source_bytes = (
        b'PK\x03\x04'
        b'kinetic-test-docx-source-content'
    )
    source_path.write_bytes(source_bytes)

    converted_path = tmp_path / 'converted.pdf'
    converted_bytes = _make_pdf(converted_path)

    conversion_calls = []

    def fake_convert_docx_to_pdf(content):
        conversion_calls.append(content)
        return ConvertedPdf(
            content=converted_bytes,
            page_count=1,
            engine='libreoffice',
            engine_version='LibreOffice Test 24.2',
        )

    monkeypatch.setattr(
        'app.services.signature_evidence_service.convert_docx_to_pdf',
        fake_convert_docx_to_pdf,
    )

    with app.app_context():
        signer_user = register_user({
            'tenant_id': tenant.id,
            'email': 'word.signer@acme.test',
            'first_name': 'Word',
            'last_name': 'Signer',
            'password': 'StrongWordSignerPass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })
        signer_user_id = inspect(signer_user).identity[0]

        signer = Employee(
            tenant_id=tenant.id,
            user_id=signer_user_id,
            employee_number='SIGN-DOCX-001',
            first_name='Word',
            last_name='Signer',
            email='word.signer@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(signer)
        db.session.flush()

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=inspect(admin_user).identity[0],
            title='Employment Agreement Word Source',
            document_type='contract',
            original_filename='employment-agreement.docx',
            stored_filename='employment-agreement.docx',
            file_path=str(source_path),
            mime_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(
                source_bytes,
            ).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()

        employee_id = signer.id
        document_id = document.id

    due_at = (datetime.utcnow() + timedelta(days=7)).replace(
        microsecond=0,
    )

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Please sign the Word employment agreement',
            'signing_mode': 'sequential',
            'assurance_level': 'standard',
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(employee_id),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )

    assert create_response.status_code == 201

    created = create_response.get_json()['data']
    recipient_id = created['recipients'][0]['id']

    assert conversion_calls == [source_bytes]
    assert len(created['fields']) == 2
    assert {
        field['page_number']
        for field in created['fields']
    } == {2}

    with app.app_context():
        artifact = SignatureArtifact.query.filter_by(
            signature_request_id=created['id'],
            artifact_type='original_document',
        ).one()

        assert artifact.mime_type == 'application/pdf'
        assert artifact.original_filename.endswith('Signing.pdf')
        assert artifact.original_filename.lower().endswith('.pdf')
        assert artifact.checksum_sha256 == hashlib.sha256(
            converted_bytes,
        ).hexdigest()

        metadata = artifact.metadata_json

        assert (
            metadata['source_original_filename']
            == 'employment-agreement.docx'
        )
        assert metadata['converted_for_signing'] is True
        assert metadata['conversion_engine'] == 'libreoffice'
        assert (
            metadata['conversion_engine_version']
            == 'LibreOffice Test 24.2'
        )
        assert metadata['conversion_page_count'] == 1
        assert (
            metadata['source_checksum_sha256']
            == hashlib.sha256(source_bytes).hexdigest()
        )
        assert metadata['source_size_bytes'] == len(source_bytes)
        assert (
            metadata['signing_snapshot_sha256']
            == artifact.checksum_sha256
        )

    _login(
        client,
        'word.signer@acme.test',
        'StrongWordSignerPass123!',
    )

    preview_response = client.get(
        f'/api/signature-requests/recipients/'
        f'{recipient_id}/document',
    )

    assert preview_response.status_code == 200
    assert preview_response.data.startswith(b'%PDF-')

    preview_pdf = PdfReader(BytesIO(preview_response.data))
    assert len(preview_pdf.pages) == 2


def test_standard_signing_rejects_unsupported_document_format(
    app,
    tenant,
    admin_user,
    tmp_path,
):
    from app.services.signature_service import create_signature_request

    source_path = tmp_path / 'unsupported.txt'
    source_bytes = b'not a supported signing document'
    source_path.write_bytes(source_bytes)

    with app.app_context():
        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=inspect(admin_user).identity[0],
            title='Unsupported signing source',
            document_type='other',
            original_filename='unsupported.txt',
            stored_filename='unsupported.txt',
            file_path=str(source_path),
            mime_type='text/plain',
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(
                source_bytes,
            ).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()

        with pytest.raises(
            ValueError,
            match=r'PDF and Word \(\.docx\)',
        ):
            create_signature_request(
                {
                    'document_id': str(document.id),
                    'assurance_level': 'standard',
                },
                tenant.id,
                admin_user,
            )


def test_docx_conversion_failure_rolls_back_signature_request(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
    monkeypatch,
):
    from app.services.document_conversion_service import (
        DocumentConversionError,
    )

    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence-docx-failure',
    )

    source_path = tmp_path / 'conversion-failure.docx'
    source_bytes = b'PK\x03\x04conversion-failure-test-source'
    source_path.write_bytes(source_bytes)

    def fail_conversion(_content):
        raise DocumentConversionError(
            'Deliberate DOCX conversion failure.',
        )

    monkeypatch.setattr(
        'app.services.signature_evidence_service.convert_docx_to_pdf',
        fail_conversion,
    )

    with app.app_context():
        signer_user = register_user({
            'tenant_id': tenant.id,
            'email': 'word.failure@acme.test',
            'first_name': 'Word',
            'last_name': 'Failure',
            'password': 'StrongWordFailurePass123!',
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

        signer = Employee(
            tenant_id=tenant.id,
            user_id=inspect(signer_user).identity[0],
            employee_number='SIGN-DOCX-FAIL-001',
            first_name='Word',
            last_name='Failure',
            email='word.failure@acme.test',
            hire_date=datetime.utcnow().date(),
            employment_status='active',
            employment_type='full_time',
        )
        db.session.add(signer)
        db.session.flush()

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=inspect(admin_user).identity[0],
            title='DOCX Conversion Failure',
            document_type='contract',
            original_filename='conversion-failure.docx',
            stored_filename='conversion-failure.docx',
            file_path=str(source_path),
            mime_type=(
                'application/vnd.openxmlformats-officedocument.'
                'wordprocessingml.document'
            ),
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(
                source_bytes,
            ).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )
        db.session.add(document)
        db.session.commit()

        employee_id = signer.id
        document_id = document.id

    due_at = (datetime.utcnow() + timedelta(days=7)).replace(
        microsecond=0,
    )

    response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': 'Conversion failure test',
            'signing_mode': 'sequential',
            'assurance_level': 'standard',
            'due_at': due_at.isoformat(),
            'recipients': [{
                'employee_id': str(employee_id),
                'role_label': 'Employee',
                'sequence': 1,
            }],
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert 'Deliberate DOCX conversion failure.' in str(payload)

    with app.app_context():
        request_count = SignatureRequest.query.filter_by(
            document_id=document_id,
        ).count()

        artifact_count = SignatureArtifact.query.join(
            SignatureRequest,
            SignatureArtifact.signature_request_id
            == SignatureRequest.id,
        ).filter(
            SignatureRequest.document_id == document_id,
        ).count()

        document = db.session.get(Document, document_id)

        assert request_count == 0
        assert artifact_count == 0
        assert document.signature_status == 'not_required'


def test_submit_route_accepts_v2_fields_rejects_foreign_field_and_stamps_final_pdf(
    client,
    app,
    tenant,
    admin_user,
    auth_headers,
    tmp_path,
):
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-v2-evidence',
    )

    source_path = tmp_path / 'signature-v2-contract.pdf'
    source_bytes = _make_pdf(source_path)

    def create_signer(
        *,
        number,
        email,
        password,
        first_name,
    ):
        user = register_user({
            'tenant_id': tenant.id,
            'email': email,
            'first_name': first_name,
            'last_name': 'Signer',
            'password': password,
            'roles': ['EMPLOYEE'],
            'email_verified_at': utcnow(),
        })

        user_id = inspect(user).identity[0]

        employee = Employee(
            tenant_id=tenant.id,
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
        db.session.flush()

        return {
            'employee_id': employee.id,
            'email': email,
            'password': password,
        }

    with app.app_context():
        signer_a = create_signer(
            number='SIGN-V2-HTTP-A',
            email='signing.v2.http.a@acme.test',
            password='StrongSigningV2AlphaPass123!',
            first_name='Amina',
        )

        signer_b = create_signer(
            number='SIGN-V2-HTTP-B',
            email='signing.v2.http.b@acme.test',
            password='StrongSigningV2BravoPass123!',
            first_name='Brian',
        )

        admin_user_id = inspect(admin_user).identity[0]

        document = Document(
            tenant_id=tenant.id,
            uploaded_by_id=admin_user_id,
            title='Signing V2 HTTP Integration Contract',
            document_type='contract',
            original_filename='signature-v2-contract.pdf',
            stored_filename='signature-v2-contract.pdf',
            file_path=str(source_path),
            mime_type='application/pdf',
            size_bytes=len(source_bytes),
            checksum_sha256=hashlib.sha256(
                source_bytes,
            ).hexdigest(),
            signature_status='not_required',
            access_level='employee',
            status='active',
        )

        db.session.add(document)
        db.session.commit()

        document_id = document.id

        signer_a_employee_id = signer_a[
            'employee_id'
        ]
        signer_b_employee_id = signer_b[
            'employee_id'
        ]

    due_at = (
        datetime.utcnow()
        + timedelta(days=7)
    ).replace(microsecond=0)

    def signing_fields(base_y):
        return [
            {
                'field_type': 'signature',
                'label': 'Electronic signature',
                'page_number': 1,
                'x': 0.08,
                'y': base_y,
                'width': 0.30,
                'height': 0.07,
                'required': True,
            },
            {
                'field_type': 'date',
                'label': 'Date signed',
                'page_number': 1,
                'x': 0.45,
                'y': base_y,
                'width': 0.19,
                'height': 0.05,
                'required': True,
            },
            {
                'field_type': 'text',
                'label': 'Work location',
                'placeholder': 'Enter work location',
                'page_number': 1,
                'x': 0.08,
                'y': base_y + 0.09,
                'width': 0.30,
                'height': 0.05,
                'required': True,
            },
            {
                'field_type': 'initials',
                'label': 'Initials',
                'placeholder': 'Enter initials',
                'page_number': 1,
                'x': 0.45,
                'y': base_y + 0.09,
                'width': 0.13,
                'height': 0.05,
                'required': True,
            },
        ]

    create_response = client.post(
        '/api/signature-requests',
        headers=auth_headers,
        json={
            'document_id': str(document_id),
            'subject': (
                'Signing fields V2 HTTP integration'
            ),
            'signing_mode': 'parallel',
            'assurance_level': 'standard',
            'due_at': due_at.isoformat(),
            'recipients': [
                {
                    'employee_id': str(
                        signer_a_employee_id,
                    ),
                    'role_label': 'Employee',
                    'sequence': 1,
                    'fields': signing_fields(0.48),
                },
                {
                    'employee_id': str(
                        signer_b_employee_id,
                    ),
                    'role_label': 'Manager',
                    'sequence': 1,
                    'fields': signing_fields(0.70),
                },
            ],
        },
    )

    assert create_response.status_code == 201

    request_data = create_response.get_json()['data']
    request_id = request_data['id']

    with app.app_context():
        recipient_a = (
            SignatureRecipient.query.filter_by(
                signature_request_id=request_id,
                employee_id=signer_a_employee_id,
            ).one()
        )

        recipient_b = (
            SignatureRecipient.query.filter_by(
                signature_request_id=request_id,
                employee_id=signer_b_employee_id,
            ).one()
        )

        recipient_a_id = str(recipient_a.id)
        recipient_b_id = str(recipient_b.id)

        fields = SignatureField.query.filter_by(
            signature_request_id=request_id,
        ).all()

        def field_id(
            recipient_id,
            field_type,
        ):
            matches = [
                field
                for field in fields
                if (
                    str(field.recipient_id)
                    == str(recipient_id)
                    and field.field_type
                    == field_type
                )
            ]

            assert len(matches) == 1

            return str(matches[0].id)

        a_text_id = field_id(
            recipient_a_id,
            'text',
        )

        a_initials_id = field_id(
            recipient_a_id,
            'initials',
        )

        b_text_id = field_id(
            recipient_b_id,
            'text',
        )

        b_initials_id = field_id(
            recipient_b_id,
            'initials',
        )

    signer_a_headers = _login(
        client,
        signer_a['email'],
        signer_a['password'],
    )

    viewed_a = client.patch(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_a_id}/viewed'
        ),
        headers=signer_a_headers,
    )

    assert viewed_a.status_code == 200

    # The ID is real and belongs to the same request and
    # tenant, but belongs to recipient B. Recipient A must
    # still be unable to write it.
    foreign_field_response = client.post(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_a_id}/submit'
        ),
        headers=signer_a_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_1',
            'fields': [
                {
                    'field_id': b_text_id,
                    'value': 'TAMPERED-FOREIGN-VALUE',
                },
            ],
        },
    )

    assert foreign_field_response.status_code == 400

    with app.app_context():
        foreign_field = (
            SignatureField.query.filter_by(
                id=b_text_id,
            ).one()
        )

        recipient_a = db.session.get(
            SignatureRecipient,
            recipient_a_id,
        )

        assert foreign_field.value is None
        assert recipient_a.status != 'signed'

    valid_a = client.post(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_a_id}/submit'
        ),
        headers=signer_a_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_1',
            'fields': [
                {
                    'field_id': a_text_id,
                    'value': 'Nairobi V2 Alpha',
                },
                {
                    'field_id': a_initials_id,
                    'value': 'AXV2',
                },
            ],
        },
    )

    assert valid_a.status_code == 200

    signer_b_headers = _login(
        client,
        signer_b['email'],
        signer_b['password'],
    )

    viewed_b = client.patch(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_b_id}/viewed'
        ),
        headers=signer_b_headers,
    )

    assert viewed_b.status_code == 200

    valid_b = client.post(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_b_id}/submit'
        ),
        headers=signer_b_headers,
        json={
            'consent': True,
            'signature_style': 'calligraphy_1',
            'fields': [
                {
                    'field_id': b_text_id,
                    'value': 'Mombasa V2 Bravo',
                },
                {
                    'field_id': b_initials_id,
                    'value': 'BXV2',
                },
            ],
        },
    )

    assert valid_b.status_code == 200

    with app.app_context():
        persisted_fields = {
            str(field.id): field
            for field in SignatureField.query.filter_by(
                signature_request_id=request_id,
            ).all()
        }

        assert (
            persisted_fields[a_text_id].value
            == 'Nairobi V2 Alpha'
        )
        assert (
            persisted_fields[a_initials_id].value
            == 'AXV2'
        )
        assert (
            persisted_fields[b_text_id].value
            == 'Mombasa V2 Bravo'
        )
        assert (
            persisted_fields[b_initials_id].value
            == 'BXV2'
        )

        completed_request = db.session.get(
            SignatureRequest,
            request_id,
        )

        assert completed_request.status == 'completed'
        assert completed_request.completed_at is not None

    signed_document = client.get(
        (
            '/api/signature-requests/recipients/'
            f'{recipient_b_id}/signed-document'
        ),
        headers=signer_b_headers,
    )

    assert signed_document.status_code == 200
    assert signed_document.data.startswith(b'%PDF')

    reader = PdfReader(
        BytesIO(signed_document.data)
    )

    rendered_text = '\n'.join(
        page.extract_text() or ''
        for page in reader.pages
    )

    assert 'Nairobi V2 Alpha' in rendered_text
    assert 'AXV2' in rendered_text
    assert 'Mombasa V2 Bravo' in rendered_text
    assert 'BXV2' in rendered_text
