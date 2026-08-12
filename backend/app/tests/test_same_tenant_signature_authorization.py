from datetime import date, datetime

from app.extensions import db
from app.models import (
    Document,
    Employee,
    SignatureDiscussion,
    SignatureDiscussionComment,
    SignatureRecipient,
    SignatureRequest,
)
from app.services.auth_service import register_user


def _login(client, email, password='StrongPass123!'):
    response = client.post(
        '/api/auth/login',
        json={'email': email, 'password': password},
    )
    assert response.status_code == 200
    csrf_cookie = client.get_cookie('csrf_access_token')
    assert csrf_cookie is not None
    return {'X-CSRF-TOKEN': csrf_cookie.value}


def _seed_multisigner_request(app, tenant_id):
    with app.app_context():
        admin = register_user({
            'tenant_id': tenant_id,
            'email': 'same-tenant.admin@acme.test',
            'first_name': 'Workflow',
            'last_name': 'Admin',
            'password': 'StrongPass123!',
            'roles': ['CLIENT_ADMIN'],
        })
        signer_a = register_user({
            'tenant_id': tenant_id,
            'email': 'same-tenant.signer-a@acme.test',
            'first_name': 'Signer',
            'last_name': 'Alpha',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })
        signer_b = register_user({
            'tenant_id': tenant_id,
            'email': 'same-tenant.signer-b@acme.test',
            'first_name': 'Signer',
            'last_name': 'Beta',
            'password': 'StrongPass123!',
            'roles': ['EMPLOYEE'],
        })

        employee_a = Employee(
            tenant_id=tenant_id,
            user_id=signer_a.id,
            employee_number='SAME-SIGN-A',
            first_name='Signer',
            last_name='Alpha',
            email='same-tenant.signer-a@acme.test',
            hire_date=date(2026, 1, 1),
        )
        employee_b = Employee(
            tenant_id=tenant_id,
            user_id=signer_b.id,
            employee_number='SAME-SIGN-B',
            first_name='Signer',
            last_name='Beta',
            email='same-tenant.signer-b@acme.test',
            hire_date=date(2026, 1, 1),
        )
        db.session.add_all([employee_a, employee_b])
        db.session.flush()

        document = Document(
            tenant_id=tenant_id,
            uploaded_by_id=admin.id,
            title='Same-tenant signer privacy contract',
            document_type='contract',
            original_filename='same-tenant-signers.pdf',
            stored_filename='same-tenant-signers-test.pdf',
            file_path='/tmp/same-tenant-signers-test.pdf',
            mime_type='application/pdf',
            size_bytes=100,
            checksum_sha256='e' * 64,
            access_level='company_admin',
            status='active',
            signature_status='pending',
        )
        db.session.add(document)
        db.session.flush()

        signature_request = SignatureRequest(
            tenant_id=tenant_id,
            document_id=document.id,
            created_by_id=admin.id,
            subject='Same-tenant signer privacy',
            signing_mode='parallel',
            status='sent',
            current_sequence=1,
            sent_at=datetime(2026, 8, 12, 9, 0, 0),
            assurance_level='standard',
        )
        db.session.add(signature_request)
        db.session.flush()

        recipient_a = SignatureRecipient(
            tenant_id=tenant_id,
            signature_request_id=signature_request.id,
            user_id=signer_a.id,
            employee_id=employee_a.id,
            name=employee_a.full_name,
            email=employee_a.email,
            sequence=1,
            role_label='Employee',
            status='notified',
        )
        recipient_b = SignatureRecipient(
            tenant_id=tenant_id,
            signature_request_id=signature_request.id,
            user_id=signer_b.id,
            employee_id=employee_b.id,
            name=employee_b.full_name,
            email=employee_b.email,
            sequence=1,
            role_label='Employee',
            status='notified',
        )
        db.session.add_all([recipient_a, recipient_b])
        db.session.commit()

        return {
            'admin_email': admin.email,
            'signer_a_email': signer_a.email,
            'signer_b_email': signer_b.email,
            'recipient_a_id': str(recipient_a.id),
            'recipient_b_id': str(recipient_b.id),
        }


def test_cosigner_cannot_access_or_modify_another_recipient_private_state(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    headers = _login(client, seeded['signer_a_email'])
    recipient_id = seeded['recipient_b_id']

    responses = {
        'details': client.get(
            f'/api/signature-requests/recipients/{recipient_id}',
        ),
        'discussion': client.get(
            f'/api/signature-requests/recipients/{recipient_id}/discussion',
        ),
        'viewed': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/viewed',
            headers=headers,
        ),
        'sign': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/sign',
            headers=headers,
            json={'signature_name': 'Signer Alpha'},
        ),
        'decline': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/decline',
            headers=headers,
            json={'reason': 'Must not alter another signer task'},
        ),
        'comment': client.post(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/comments',
            headers=headers,
            json={'body': 'Must not comment on another signer discussion'},
        ),
        'resolve': client.patch(
            f'/api/signature-requests/recipients/{recipient_id}/discussion/resolve',
            headers=headers,
        ),
    }

    assert {
        action: response.status_code
        for action, response in responses.items()
    } == {
        'details': 403,
        'discussion': 403,
        'viewed': 403,
        'sign': 403,
        'decline': 403,
        'comment': 403,
        'resolve': 403,
    }

    with app.app_context():
        assert SignatureDiscussion.query.filter_by(
            recipient_id=recipient_id,
        ).count() == 0
        assert SignatureDiscussionComment.query.count() == 0


def test_recipient_can_access_and_manage_own_discussion(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    headers = _login(client, seeded['signer_b_email'])
    recipient_id = seeded['recipient_b_id']

    details = client.get(
        f'/api/signature-requests/recipients/{recipient_id}',
    )
    discussion = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/discussion',
    )
    comment = client.post(
        f'/api/signature-requests/recipients/{recipient_id}/discussion/comments',
        headers=headers,
        json={'body': 'I need clarification before signing.'},
    )
    resolve = client.patch(
        f'/api/signature-requests/recipients/{recipient_id}/discussion/resolve',
        headers=headers,
    )

    assert details.status_code == 200
    assert discussion.status_code == 200
    assert comment.status_code == 201
    assert resolve.status_code == 200


def test_request_admin_retains_recipient_discussion_access(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    headers = _login(client, seeded['admin_email'])
    recipient_id = seeded['recipient_b_id']

    details = client.get(
        f'/api/signature-requests/recipients/{recipient_id}',
    )
    discussion = client.get(
        f'/api/signature-requests/recipients/{recipient_id}/discussion',
    )
    comment = client.post(
        f'/api/signature-requests/recipients/{recipient_id}/discussion/comments',
        headers=headers,
        json={'body': 'Administrator response to the signer.'},
    )
    resolve = client.patch(
        f'/api/signature-requests/recipients/{recipient_id}/discussion/resolve',
        headers=headers,
    )

    assert details.status_code == 200
    assert discussion.status_code == 200
    assert comment.status_code == 201
    assert resolve.status_code == 200
