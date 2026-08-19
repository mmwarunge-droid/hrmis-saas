from datetime import date, datetime

from app.extensions import db
from app.models import (
    Document,
    Employee,
    Notification,
    SignatureDiscussion,
    SignatureDiscussionComment,
    SignatureDiscussionCommentRevision,
    SignatureDiscussionParticipant,
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
            'admin_user_id': str(admin.id),
            'signer_a_email': signer_a.email,
            'signer_a_user_id': str(signer_a.id),
            'signer_b_email': signer_b.email,
            'signer_b_user_id': str(signer_b.id),
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



def test_mentioned_employee_gets_discussion_only_access(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    recipient_id = seeded['recipient_b_id']

    signer_b_headers = _login(
        client,
        seeded['signer_b_email'],
    )

    created = client.post(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments'
        ),
        headers=signer_b_headers,
        json={
            'body': (
                'Can @Signer Alpha help us clarify '
                'this requirement?'
            ),
            'mentioned_user_ids': [
                seeded['signer_a_user_id'],
            ],
        },
    )
    assert created.status_code == 201

    with app.app_context():
        discussion = SignatureDiscussion.query.filter_by(
            recipient_id=recipient_id,
        ).one()

        comment = SignatureDiscussionComment.query.filter_by(
            discussion_id=discussion.id,
        ).one()

        comment_id = str(comment.id)

        participant = (
            SignatureDiscussionParticipant.query.filter_by(
                discussion_id=discussion.id,
                user_id=seeded['signer_a_user_id'],
            ).one()
        )
        assert participant.source == 'mention'
        assert (
            str(participant.added_by_user_id)
            == seeded['signer_b_user_id']
        )

        mention_notification = (
            Notification.query.filter_by(
                user_id=seeded['signer_a_user_id'],
                notification_type='signature_discussion',
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert mention_notification is not None
        assert mention_notification.action_url == (
            f'/signature-discussions/{recipient_id}'
        )
        assert (
            mention_notification.metadata_json[
                'discussion_only'
            ]
            is True
        )

        owner_notification = (
            Notification.query.filter_by(
                user_id=seeded['admin_user_id'],
                notification_type='signature_discussion',
            )
            .order_by(Notification.created_at.desc())
            .first()
        )
        assert owner_notification is not None
        assert owner_notification.action_url == (
            f'/signature-tasks/{recipient_id}'
        )

    follow_up = client.post(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments'
        ),
        headers=signer_b_headers,
        json={
            'body': (
                'A follow-up for everyone already '
                'participating in this discussion.'
            ),
            'mentioned_user_ids': [],
        },
    )
    assert follow_up.status_code == 201

    with app.app_context():
        participant_notifications = (
            Notification.query.filter_by(
                user_id=seeded['signer_a_user_id'],
                notification_type='signature_discussion',
            ).all()
        )

        assert len(participant_notifications) == 2
        assert {
            notification.action_url
            for notification in participant_notifications
        } == {
            f'/signature-discussions/{recipient_id}',
        }
        assert all(
            notification.metadata_json.get(
                'discussion_only'
            ) is True
            for notification in participant_notifications
        )

    signer_a_headers = _login(
        client,
        seeded['signer_a_email'],
    )

    discussion_response = client.get(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion'
        ),
    )
    assert discussion_response.status_code == 200

    reply = client.post(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments'
        ),
        headers=signer_a_headers,
        json={
            'body': (
                'I can help clarify the requirement.'
            ),
            'mentioned_user_ids': [],
        },
    )
    assert reply.status_code == 201

    mention_search = client.get(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/mentions?q=Signer'
        ),
    )
    assert mention_search.status_code == 200

    forbidden = {
        'details': client.get(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}'
            ),
        ),
        'document': client.get(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/document'
            ),
        ),
        'sign': client.patch(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/sign'
            ),
            headers=signer_a_headers,
            json={
                'signature_name': 'Signer Alpha',
            },
        ),
        'decline': client.patch(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/decline'
            ),
            headers=signer_a_headers,
            json={
                'reason': (
                    'Mentioned participant cannot decline.'
                ),
            },
        ),
        'resolve': client.patch(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/discussion/resolve'
            ),
            headers=signer_a_headers,
        ),
        'edit_other_comment': client.patch(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/discussion/comments/'
                f'{comment_id}'
            ),
            headers=signer_a_headers,
            json={
                'body': (
                    'A participant must not edit '
                    'another author comment.'
                ),
                'mentioned_user_ids': [],
            },
        ),
        'delete_other_comment': client.delete(
            (
                f'/api/signature-requests/recipients/'
                f'{recipient_id}/discussion/comments/'
                f'{comment_id}'
            ),
            headers=signer_a_headers,
        ),
    }

    assert {
        action: response.status_code
        for action, response in forbidden.items()
    } == {
        'details': 403,
        'document': 403,
        'sign': 403,
        'decline': 403,
        'resolve': 403,
        'edit_other_comment': 403,
        'delete_other_comment': 403,
    }


def test_comment_edit_and_delete_preserve_revision_history(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    recipient_id = seeded['recipient_b_id']

    headers = _login(
        client,
        seeded['signer_b_email'],
    )

    original_body = (
        'Please ask @Signer Alpha about clause five.'
    )
    edited_body = (
        'Please ask @Signer Alpha about clause six instead.'
    )

    created = client.post(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments'
        ),
        headers=headers,
        json={
            'body': original_body,
            'mentioned_user_ids': [
                seeded['signer_a_user_id'],
            ],
        },
    )
    assert created.status_code == 201

    with app.app_context():
        discussion = SignatureDiscussion.query.filter_by(
            recipient_id=recipient_id,
        ).one()

        comment = SignatureDiscussionComment.query.filter_by(
            discussion_id=discussion.id,
        ).one()

        comment_id = str(comment.id)

        revisions = (
            SignatureDiscussionCommentRevision.query
            .filter_by(comment_id=comment.id)
            .order_by(
                SignatureDiscussionCommentRevision.occurred_at.asc()
            )
            .all()
        )

        assert len(revisions) == 1
        assert revisions[0].revision_type == 'created'
        assert revisions[0].body == original_body
        assert revisions[0].mentioned_user_ids_json == [
            seeded['signer_a_user_id'],
        ]

    updated = client.patch(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments/'
            f'{comment_id}'
        ),
        headers=headers,
        json={
            'body': edited_body,
            'mentioned_user_ids': [
                seeded['signer_a_user_id'],
            ],
        },
    )
    assert updated.status_code == 200

    with app.app_context():
        comment = db.session.get(
            SignatureDiscussionComment,
            comment_id,
        )

        assert comment.body == edited_body
        assert comment.edited_at is not None
        assert comment.deleted_at is None

        revisions = (
            SignatureDiscussionCommentRevision.query
            .filter_by(comment_id=comment.id)
            .order_by(
                SignatureDiscussionCommentRevision.occurred_at.asc()
            )
            .all()
        )

        assert [
            revision.revision_type
            for revision in revisions
        ] == [
            'created',
            'edited',
        ]
        assert revisions[0].body == original_body
        assert revisions[1].body == edited_body

    deleted = client.delete(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments/'
            f'{comment_id}'
        ),
        headers=headers,
    )
    assert deleted.status_code == 200

    with app.app_context():
        comment = db.session.get(
            SignatureDiscussionComment,
            comment_id,
        )

        # Soft deletion: sensitive history remains persisted.
        assert comment.deleted_at is not None
        assert (
            str(comment.deleted_by_user_id)
            == seeded['signer_b_user_id']
        )
        assert comment.body == edited_body
        assert comment.mentioned_user_ids_json == [
            seeded['signer_a_user_id'],
        ]

        revisions = (
            SignatureDiscussionCommentRevision.query
            .filter_by(comment_id=comment.id)
            .order_by(
                SignatureDiscussionCommentRevision.occurred_at.asc()
            )
            .all()
        )

        assert [
            revision.revision_type
            for revision in revisions
        ] == [
            'created',
            'edited',
            'deleted',
        ]
        assert revisions[2].body == edited_body

    visible = client.get(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion'
        ),
    )
    assert visible.status_code == 200

    payload = visible.get_json()['data']
    deleted_comment = next(
        item
        for item in payload['comments']
        if item['id'] == comment_id
    )

    assert deleted_comment['is_deleted'] is True
    assert deleted_comment['body'] is None
    assert deleted_comment['mentioned_user_ids'] == []


def test_plain_text_mention_cannot_grant_discussion_access(
    app,
    client,
    tenant,
):
    seeded = _seed_multisigner_request(app, tenant.id)
    recipient_id = seeded['recipient_b_id']

    signer_b_headers = _login(
        client,
        seeded['signer_b_email'],
    )

    created = client.post(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion/comments'
        ),
        headers=signer_b_headers,
        json={
            'body': (
                f"Can @{seeded['signer_a_email']} "
                'review this requirement?'
            ),
            # Deliberately omitted. Free-form text alone must
            # never grant discussion authorization.
        },
    )
    assert created.status_code == 201

    with app.app_context():
        discussion = SignatureDiscussion.query.filter_by(
            recipient_id=recipient_id,
        ).one()

        participant = (
            SignatureDiscussionParticipant.query.filter_by(
                discussion_id=discussion.id,
                user_id=seeded['signer_a_user_id'],
            ).first()
        )

        assert participant is None

    _login(
        client,
        seeded['signer_a_email'],
    )

    discussion_response = client.get(
        (
            f'/api/signature-requests/recipients/'
            f'{recipient_id}/discussion'
        ),
    )

    assert discussion_response.status_code == 403
