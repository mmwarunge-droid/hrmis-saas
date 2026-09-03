import hashlib
import os
import threading
from uuid import uuid4

import pytest
from reportlab.pdfgen import canvas

from app import create_app
from app.config import DevelopmentConfig
from app.extensions import db
from app.models import (
    Document,
    SignatureArtifact,
    SignatureEvent,
    SignatureField,
    SignatureRecipient,
    SignatureRequest,
    Tenant,
    User,
)
from app.models.base import utcnow
from app.services import signature_service
from app.services.auth_service import register_user
from app.services.signature_evidence_service import (
    capture_source_artifact,
)
from app.services.signature_service import mark_recipient_signed


def _write_source_pdf(path):
    pdf = canvas.Canvas(str(path))
    pdf.drawString(
        72,
        720,
        'Kinetic parallel signing concurrency test',
    )
    pdf.save()
    return path.read_bytes()


@pytest.fixture()
def postgres_parallel_signing_app(tmp_path):
    database_url = os.getenv('HRMIS_PG_TEST_URL')

    if not database_url:
        pytest.skip(
            'HRMIS_PG_TEST_URL is required for '
            'PostgreSQL concurrency tests'
        )

    original_database_url = (
        DevelopmentConfig.SQLALCHEMY_DATABASE_URI
    )
    DevelopmentConfig.SQLALCHEMY_DATABASE_URI = (
        database_url
    )

    app = create_app('development')
    app.config['TESTING'] = True
    app.config['SIGNATURE_EVIDENCE_STORAGE'] = 'local'
    app.config['SIGNATURE_EVIDENCE_FOLDER'] = str(
        tmp_path / 'signature-evidence'
    )

    tenant_id = None
    user_ids = []

    try:
        with app.app_context():
            marker = uuid4().hex

            tenant = Tenant(
                name=(
                    'Parallel Signing Concurrency '
                    f'{marker}'
                ),
                slug=f'parallel-signing-{marker}',
                country='Kenya',
            )

            db.session.add(tenant)
            db.session.flush()

            tenant_id = tenant.id

            users = []

            for label, first_name in (
                ('alpha', 'Amina'),
                ('bravo', 'Brian'),
            ):
                user = register_user(
                    {
                        'tenant_id': tenant.id,
                        'email': (
                            f'parallel-{label}-{marker}'
                            '@example.test'
                        ),
                        'first_name': first_name,
                        'last_name': 'Concurrency',
                        'password': (
                            'StrongParallelConcurrencyPass123!'
                        ),
                        'roles': ['EMPLOYEE'],
                        'email_verified_at': utcnow(),
                    },
                    commit=False,
                )

                users.append(user)

            db.session.flush()

            user_ids = [
                user.id
                for user in users
            ]

            source_path = (
                tmp_path
                / f'parallel-{marker}.pdf'
            )

            source_bytes = _write_source_pdf(
                source_path
            )
            checksum = hashlib.sha256(
                source_bytes
            ).hexdigest()

            document = Document(
                tenant_id=tenant.id,
                uploaded_by_id=users[0].id,
                title='Parallel Signing Contract',
                document_type='contract',
                original_filename=source_path.name,
                stored_filename=source_path.name,
                file_path=str(source_path),
                mime_type='application/pdf',
                size_bytes=len(source_bytes),
                checksum_sha256=checksum,
                signature_status='not_required',
                access_level='employee',
                status='active',
            )

            db.session.add(document)
            db.session.flush()

            signature_request = SignatureRequest(
                tenant_id=tenant.id,
                document_id=document.id,
                created_by_id=users[0].id,
                subject='Parallel signing concurrency',
                signing_mode='parallel',
                status='in_progress',
                current_sequence=1,
                sent_at=utcnow(),
                assurance_level='standard',
            )

            db.session.add(signature_request)
            db.session.flush()

            recipients = []

            for index, user in enumerate(
                users,
                start=1,
            ):
                recipient = SignatureRecipient(
                    tenant_id=tenant.id,
                    signature_request_id=(
                        signature_request.id
                    ),
                    user_id=user.id,
                    name=(
                        f'{user.first_name} '
                        f'{user.last_name}'
                    ),
                    email=user.email,
                    role_label=(
                        'Employee'
                        if index == 1
                        else 'Manager'
                    ),
                    sequence=1,
                    status='viewed',
                    viewed_at=utcnow(),
                )

                db.session.add(recipient)
                recipients.append(recipient)

            db.session.flush()

            text_field_ids = []

            for index, recipient in enumerate(
                recipients,
            ):
                base_y = 0.25 + (index * 0.30)

                signature_field = SignatureField(
                    tenant_id=tenant.id,
                    signature_request_id=(
                        signature_request.id
                    ),
                    recipient_id=recipient.id,
                    field_type='signature',
                    label='Electronic signature',
                    page_number=1,
                    x=0.08,
                    y=base_y,
                    width=0.30,
                    height=0.06,
                    required=True,
                )

                date_field = SignatureField(
                    tenant_id=tenant.id,
                    signature_request_id=(
                        signature_request.id
                    ),
                    recipient_id=recipient.id,
                    field_type='date',
                    label='Date signed',
                    page_number=1,
                    x=0.45,
                    y=base_y,
                    width=0.20,
                    height=0.05,
                    required=True,
                )

                text_field = SignatureField(
                    tenant_id=tenant.id,
                    signature_request_id=(
                        signature_request.id
                    ),
                    recipient_id=recipient.id,
                    field_type='text',
                    label='Work location',
                    page_number=1,
                    x=0.08,
                    y=base_y + 0.09,
                    width=0.30,
                    height=0.05,
                    required=True,
                )

                db.session.add_all([
                    signature_field,
                    date_field,
                    text_field,
                ])
                db.session.flush()

                text_field_ids.append(
                    text_field.id
                )

            # Exercise the real Kinetic request lifecycle rather
            # than fabricating an evidence row. Production request
            # creation captures an immutable source artifact before
            # any recipient can sign, and the native PDF renderer
            # reads that captured artifact during finalization.
            source_artifact = capture_source_artifact(
                signature_request,
            )

            assert source_artifact is not None
            assert (
                source_artifact.artifact_type
                == 'original_document'
            )
            assert (
                source_artifact.checksum_sha256
                == checksum
            )

            db.session.commit()

            state = {
                'request_id': signature_request.id,
                'recipient_ids': [
                    recipient.id
                    for recipient in recipients
                ],
                'user_ids': user_ids,
                'text_field_ids': text_field_ids,
                'values': [
                    'Nairobi concurrent alpha',
                    'Mombasa concurrent bravo',
                ],
            }

        yield app, state

    finally:
        with app.app_context():
            db.session.remove()

            for user_id in user_ids:
                user = db.session.get(
                    User,
                    user_id,
                )

                if user is not None:
                    db.session.delete(user)

            if tenant_id is not None:
                tenant = db.session.get(
                    Tenant,
                    tenant_id,
                )

                if tenant is not None:
                    db.session.delete(tenant)

            db.session.commit()

        DevelopmentConfig.SQLALCHEMY_DATABASE_URI = (
            original_database_url
        )


def test_parallel_signers_finalize_exactly_once(
    postgres_parallel_signing_app,
    monkeypatch,
):
    app, state = postgres_parallel_signing_app

    # Suppress mail delivery only. Real signature events,
    # field persistence, PDF generation and final artifact
    # creation remain active.
    monkeypatch.setattr(
        signature_service,
        '_notify_admin',
        lambda *args, **kwargs: None,
    )

    # mark_recipient_signed() intentionally suppresses
    # NativeSignatureError under TESTING. Capture that exact
    # failure here so the PostgreSQL integration test cannot
    # falsely report a completed request without its immutable
    # signed-document artifact.
    artifact_errors = []
    original_artifact_creator = (
        signature_service.create_signed_document_artifact
    )

    def recording_artifact_creator(signature_request):
        try:
            return original_artifact_creator(
                signature_request,
            )
        except Exception as exc:
            artifact_errors.append(
                (
                    type(exc).__name__,
                    str(exc),
                )
            )
            raise

    monkeypatch.setattr(
        signature_service,
        'create_signed_document_artifact',
        recording_artifact_creator,
    )

    with app.app_context():
        session_class = type(db.session())

    original_commit = session_class.commit

    # Current implementation has no request-level serialization.
    #
    # Holding both worker commits until both transactions reach
    # commit guarantees that each completion check happens while
    # the other recipient's signature is still uncommitted.
    #
    # The timeout is intentional: once the production code gains
    # a request-row lock, one worker will be blocked on that lock.
    # The first worker is then allowed to commit, releasing the
    # lock so the second can observe the committed signature and
    # perform finalization.
    commit_barrier = threading.Barrier(2)

    def synchronized_commit(session):
        try:
            commit_barrier.wait(timeout=1.5)
        except threading.BrokenBarrierError:
            pass

        return original_commit(session)

    monkeypatch.setattr(
        session_class,
        'commit',
        synchronized_commit,
    )

    start_barrier = threading.Barrier(2)
    worker_errors = []

    def sign_recipient(index):
        try:
            with app.app_context():
                recipient = db.session.get(
                    SignatureRecipient,
                    state['recipient_ids'][index],
                )

                actor = db.session.get(
                    User,
                    state['user_ids'][index],
                )

                start_barrier.wait(timeout=10)

                mark_recipient_signed(
                    recipient,
                    actor,
                    consent=True,
                    signature_style='calligraphy_1',
                    field_values=[
                        {
                            'field_id': str(
                                state[
                                    'text_field_ids'
                                ][index]
                            ),
                            'value': (
                                state['values'][index]
                            ),
                        },
                    ],
                )

        except Exception as exc:
            worker_errors.append(
                (
                    index,
                    type(exc).__name__,
                    str(exc),
                )
            )

        finally:
            with app.app_context():
                db.session.remove()

    workers = [
        threading.Thread(
            target=sign_recipient,
            args=(0,),
            name='parallel-signer-a',
        ),
        threading.Thread(
            target=sign_recipient,
            args=(1,),
            name='parallel-signer-b',
        ),
    ]

    for worker in workers:
        worker.start()

    for worker in workers:
        worker.join(timeout=20)

    assert not any(
        worker.is_alive()
        for worker in workers
    )

    assert worker_errors == []
    assert artifact_errors == []

    with app.app_context():
        db.session.remove()

        recipients = (
            SignatureRecipient.query.filter_by(
                signature_request_id=(
                    state['request_id']
                ),
            )
            .order_by(
                SignatureRecipient.email.asc(),
            )
            .all()
        )

        assert len(recipients) == 2
        assert all(
            recipient.status == 'signed'
            for recipient in recipients
        )

        for field_id, expected_value in zip(
            state['text_field_ids'],
            state['values'],
            strict=False,
        ):
            field = db.session.get(
                SignatureField,
                field_id,
            )

            assert field.value == expected_value
            assert field.completed_at is not None

        signature_request = db.session.get(
            SignatureRequest,
            state['request_id'],
        )

        signed_artifacts = (
            SignatureArtifact.query.filter_by(
                signature_request_id=(
                    state['request_id']
                ),
                artifact_type='signed_document',
            ).all()
        )

        completion_events = (
            SignatureEvent.query.filter_by(
                signature_request_id=(
                    state['request_id']
                ),
                event_type=(
                    'signature.request_completed'
                ),
            ).all()
        )

        assert signature_request.status == 'completed'
        assert signature_request.completed_at is not None
        assert len(signed_artifacts) == 1
        assert len(completion_events) == 1
