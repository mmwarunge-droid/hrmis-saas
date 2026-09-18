from pathlib import Path
from datetime import timedelta

import pytest

from app.extensions import db
from app.models import Document, Notification, SignatureArtifact, SignatureEvent, SignatureRecipient, SignatureRequest
from app.models.base import utcnow
from app.services.native_signature_service import NativeSignatureError
from app.tests.test_hr_native_execution import setup_execution as execution_fixture, create, login_signer  # noqa: F401


@pytest.fixture()
def setup_execution(app, request):
    return request.getfixturevalue("execution_fixture")



@pytest.fixture()
def issued(client, auth_headers, setup_execution):
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 201, response.json
    workflow = response.json['data']
    headers = login_signer(client)
    return workflow, headers, f"/api/signature-requests/recipients/{workflow['recipients'][0]['id']}"


def test_view_retry_does_not_duplicate_events_or_notifications(app, client, issued):
    workflow, headers, url = issued
    assert client.patch(url + '/viewed', headers=headers).status_code == 200
    counts = (Notification.query.count(), SignatureEvent.query.count())
    assert client.patch(url + '/viewed', headers=headers).status_code == 200
    assert (Notification.query.count(), SignatureEvent.query.count()) == counts


def test_submit_retry_preserves_artifact_and_completion_notifications(app, client, issued):
    workflow, headers, url = issued
    result = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert result.status_code == 200, result.json
    counts = (Notification.query.count(), SignatureEvent.query.count(), SignatureArtifact.query.count())
    artifact = SignatureArtifact.query.filter_by(signature_request_id=workflow['id'], artifact_type='signed_document').one()
    checksum = artifact.checksum_sha256
    result = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert result.status_code == 200, result.json
    assert (Notification.query.count(), SignatureEvent.query.count(), SignatureArtifact.query.count()) == counts
    assert artifact.checksum_sha256 == checksum
    assert client.get(url + '/signed-document').data.startswith(b'%PDF-')


def test_render_failure_rolls_back_signature_even_in_testing(app, client, issued, monkeypatch):
    workflow, headers, url = issued
    counts = (Notification.query.count(), SignatureEvent.query.count())
    def fail_render(_request):
        raise NativeSignatureError('PDF rendering unavailable')
    monkeypatch.setattr('app.services.signature_service.create_signed_document_artifact', fail_render)
    response = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert response.status_code == 409, response.json
    request = db.session.get(SignatureRequest, workflow['id'])
    assert request.status == 'sent'
    assert request.completed_at is None
    assert request.document.signature_status == 'pending'
    assert request.recipients[0].signed_at is None
    assert all(f.completed_at is None for f in request.fields)
    assert SignatureArtifact.query.filter_by(artifact_type='signed_document').count() == 0
    assert (Notification.query.count(), SignatureEvent.query.count()) == counts


def test_missing_snapshot_open_and_submit_are_controlled(app, client, issued):
    workflow, headers, url = issued
    artifact = SignatureArtifact.query.filter_by(signature_request_id=workflow['id'], artifact_type='original_document').one()
    Path(artifact.file_path).unlink()
    assert client.get(url + '/document').status_code == 409
    response = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert response.status_code == 409, response.json
    assert db.session.get(SignatureRequest, workflow['id']).status == 'sent'


@pytest.mark.parametrize('action', ['viewed', 'submit'])
def test_overdue_recipient_cannot_mutate_before_expiry_job(app, client, issued, action):
    workflow, headers, url = issued
    request = db.session.get(SignatureRequest, workflow['id'])
    request.due_at = utcnow() - timedelta(seconds=1)
    request.recipients[0].due_at = request.due_at
    db.session.commit()
    if action == 'viewed':
        result = client.patch(url + '/viewed', headers=headers)
    else:
        result = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert result.status_code == 409, result.json
    assert db.session.get(SignatureRecipient, workflow['recipients'][0]['id']).status == 'notified'


@pytest.mark.parametrize('path', [
    '/signature-requests/invalid', '/signature-requests/recipients/invalid',
    '/documents/invalid', '/notifications/invalid/read',
])
def test_invalid_resource_id_is_controlled(client, auth_headers, path):
    response = client.patch('/api' + path, headers=auth_headers) if path.endswith('/read') else client.get('/api' + path)
    assert response.status_code == 404


def test_missing_library_file_returns_controlled_error(app, client, auth_headers, setup_execution):
    app.config["UPLOAD_FOLDER"] = str(setup_execution["source"].parent)
    setup_execution['source'].unlink()
    response = client.get(f"/api/documents/{setup_execution['document']}/download")
    assert response.status_code == 409


def test_missing_source_rejects_assignment(app, client, auth_headers, setup_execution):
    setup_execution['source'].unlink()
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 400, response.json
    assert SignatureRequest.query.count() == 0


def test_smtp_multiline_title_does_not_abort_assignment(app, client, auth_headers, setup_execution, monkeypatch):
    sent = []
    class SMTP:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def send_message(self, message):
            sent.append(message)
    monkeypatch.setattr('app.utils.email.smtplib.SMTP', SMTP)
    app.config.update(MAIL_TRANSPORT='smtp', MAIL_SMTP_USE_TLS=False, MAIL_SMTP_USERNAME=None)
    document = db.session.get(Document, setup_execution['document'])
    document.title = 'Employment contract\nPlease sign'
    db.session.commit()
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 201, response.json
    assert len(sent) == 1
    assert '\n' not in str(sent[0]['Subject'])


def test_failed_assignment_sends_no_email_and_cleans_snapshot(app, client, auth_headers, setup_execution, monkeypatch):
    before = len(app.extensions.get('mail_outbox', []))
    from app.services import signature_service
    original = signature_service._notify_recipient
    def fail_after_notification(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError('Simulated failure before commit')
    monkeypatch.setattr(signature_service, '_notify_recipient', fail_after_notification)
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 400
    assert SignatureRequest.query.count() == 0
    assert SignatureArtifact.query.count() == 0
    assert Notification.query.count() == 0
    assert len(app.extensions.get('mail_outbox', [])) == before
    assert list(Path(app.config['SIGNATURE_EVIDENCE_FOLDER']).rglob('*.pdf')) == []


def test_email_failure_keeps_request_and_bell_notification(app, client, auth_headers, setup_execution, monkeypatch):
    from app.utils.email import EmailDeliveryError
    def fail_email(*args, **kwargs):
        raise EmailDeliveryError('Temporary SMTP outage')
    monkeypatch.setattr('app.services.signature_service.send_email', fail_email)
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 201, response.json
    workflow = response.json['data']
    assert db.session.get(SignatureRequest, workflow['id']).status == 'sent'
    assert Notification.query.count() == 1
    assert SignatureEvent.query.filter_by(event_type='signature.email_delivery_failed').count() == 1
    headers = login_signer(client)
    url = '/api/signature-requests/recipients/' + workflow['recipients'][0]['id']
    result = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert result.status_code == 200, result.json
    assert db.session.get(SignatureRequest, workflow['id']).status == 'completed'
    assert client.get(url + '/signed-document').status_code == 200


def test_failed_finalization_cleans_new_pdf_and_all_signature_state(app, client, issued, monkeypatch):
    workflow, headers, url = issued
    from app.services import signature_service
    before_files = set(Path(app.config['SIGNATURE_EVIDENCE_FOLDER']).rglob('*.pdf'))
    original = signature_service._notify_admin
    def fail_before_commit(*args, **kwargs):
        original(*args, **kwargs)
        raise ValueError('Simulated database-bound validation failure')
    monkeypatch.setattr(signature_service, '_notify_admin', fail_before_commit)
    response = client.post(url + '/submit', headers=headers, json={'consent': True})
    assert response.status_code == 400
    assert set(Path(app.config['SIGNATURE_EVIDENCE_FOLDER']).rglob('*.pdf')) == before_files
    assert SignatureArtifact.query.filter_by(artifact_type='signed_document').count() == 0
    assert db.session.get(SignatureRequest, workflow['id']).status == 'sent'


def test_notification_rollback_sends_no_email(app, tenant, admin_user):
    from app.services.notification_service import create_notification
    before = len(app.extensions.get('mail_outbox', []))
    from sqlalchemy import inspect
    create_notification(tenant_id=tenant.id, user_id=inspect(admin_user).identity[0], title='Temporary task', action_url='/tasks')
    db.session.rollback()
    assert len(app.extensions.get('mail_outbox', [])) == before
    assert Notification.query.count() == 0


@pytest.mark.parametrize('method', ['generated', 'typed', 'drawn', 'uploaded'])
def test_all_signature_inputs_generate_a_real_pdf(app, client, issued, method):
    from io import BytesIO
    from pypdf import PdfReader
    from app.tests.test_hr_native_execution import image_data
    workflow, headers, url = issued
    payload = {'consent': True, 'signature_input': method}
    if method == 'typed':
        payload['signature_text'] = 'Jane Doe signature'
    if method in {'drawn', 'uploaded'}:
        payload['signature_image'] = image_data()
    response = client.post(url + '/submit', headers=headers, json=payload)
    assert response.status_code == 200, response.json
    result = client.get(url + '/signed-document')
    assert result.status_code == 200
    reader = PdfReader(BytesIO(result.data))
    assert reader.metadata['/KineticVersionID'] == workflow['id']
    if method in {'drawn', 'uploaded'}:
        assert '/XObject' in reader.pages[0]['/Resources']
    else:
        assert ('Jane Doe signature' if method == 'typed' else 'J.Doe') in reader.pages[0].extract_text()


def test_foreign_tenant_cannot_access_sign_or_download(app, client, issued):
    from app.models import Tenant
    from app.services.auth_service import register_user
    workflow, _, url = issued
    tenant = Tenant(name='Other tenant', slug='foreign-stability', country='Kenya')
    db.session.add(tenant)
    db.session.flush()
    register_user({'tenant_id': tenant.id, 'email': 'foreign@other.test',
        'first_name': 'Other', 'last_name': 'User', 'password': 'StrongForeignPass123!',
        'roles': ['CLIENT_ADMIN'], 'email_verified_at': utcnow()})
    login = client.post('/api/auth/login', json={'email': 'foreign@other.test', 'password': 'StrongForeignPass123!'})
    assert login.status_code == 200
    headers = {'X-CSRF-TOKEN': client.get_cookie('csrf_access_token').value}
    for suffix in ['', '/document', '/signed-document']:
        assert client.get(url + suffix).status_code == 404
    assert client.post(url + '/submit', headers=headers, json={'consent': True}).status_code == 404
    assert client.patch(url + '/viewed', headers=headers).status_code == 404
    assert client.get('/api/documents/' + workflow['document_id']).status_code == 404
    assert client.get('/api/notifications').json['data']['items'] == []


@pytest.mark.parametrize('path', ['/signature-requests?document_id=invalid', '/documents?employee_id=invalid'])
def test_invalid_query_identifier_is_controlled(client, auth_headers, path):
    assert client.get('/api' + path).status_code == 422


def test_empty_upload_and_storage_outage_are_controlled(app, client, auth_headers, tmp_path, monkeypatch):
    from io import BytesIO
    empty = client.post('/api/documents/upload', headers=auth_headers, data={
        'title': 'Empty contract', 'document_type': 'contract', 'file': (BytesIO(b''), 'empty.pdf'),
    })
    assert empty.status_code == 400
    def fail_storage(*args, **kwargs):
        raise OSError('Private storage location /do/not/expose')
    monkeypatch.setattr('app.services.document_service.save_document_file', fail_storage)
    unavailable = client.post('/api/documents/upload', headers=auth_headers, data={
        'title': 'Contract', 'document_type': 'contract', 'file': (BytesIO(b'%PDF-1.4'), 'test.pdf'),
    })
    assert unavailable.status_code == 503
    assert '/do/not/expose' not in unavailable.get_data(as_text=True)
    assert Document.query.count() == 0


def test_platform_requester_receives_own_cross_organization_notifications(app, client, tenant):
    from app.services.auth_service import register_user
    from app.services.notification_service import create_notification
    user = register_user({'email': 'platform@kinetic.test', 'first_name': 'Platform', 'last_name': 'Admin',
        'password': 'StrongPlatformPass123!', 'roles': ['SUPER_ADMIN']})
    notification = create_notification(tenant_id=tenant.id, user_id=user.id, title='Signature completed', commit=True)
    assert notification is not None
    # Issue test auth using the same helpers as tenant tests; MFA is separately covered.
    from flask_jwt_extended import set_access_cookies
    from app.services.session_service import create_auth_session
    from flask import make_response
    response = make_response()
    _, access_token, _ = create_auth_session(user, mfa_verified=True)
    set_access_cookies(response, access_token)
    from http.cookies import SimpleCookie
    for header in response.headers.getlist('Set-Cookie'):
        cookies = SimpleCookie(header)
        for key, value in cookies.items():
            client.set_cookie(key, value.value)
    feed = client.get('/api/notifications')
    assert feed.status_code == 200
    assert any(item['id'] == str(notification.id) for item in feed.json['data']['items'])



def test_s3_dependency_failure_rolls_back_assignment(app, client, auth_headers, setup_execution, monkeypatch):
    from botocore.exceptions import ClientError
    class UnavailableS3:
        def put_object(self, **kwargs):
            raise ClientError({'Error': {'Code': 'ServiceUnavailable', 'Message': 'unavailable'}}, 'PutObject')
        def delete_object(self, **kwargs):
            return {}
    monkeypatch.setattr('app.utils.signature_evidence_storage._s3_client', lambda: UnavailableS3())
    app.config.update(SIGNATURE_EVIDENCE_STORAGE='s3', SIGNATURE_EVIDENCE_S3_BUCKET='test-evidence')
    response = create(client, auth_headers, setup_execution)
    assert response.status_code == 503, response.json
    assert SignatureRequest.query.count() == 0
    assert SignatureArtifact.query.count() == 0
    assert Notification.query.count() == 0
