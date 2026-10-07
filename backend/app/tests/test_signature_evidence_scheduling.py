"""Run with HRMIS_EVIDENCE_TEST_URL pointing ONLY at a disposable PostgreSQL DB.
The app fixture creates/drops its tables. Never supply a production URL.
"""
import os
import threading
import time
from uuid import uuid4
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text

import signature_evidence_worker as worker
from app import create_app
from app.config import TestingConfig
from app.extensions import db
from app.models import SignatureArtifact, SignatureEvent, SignatureRequest
from app.models.base import utcnow
from app.services import signature_evidence_service as service
from app.services.rbac_service import seed_roles_permissions
from app.tests.test_signature_evidence_ingestion import (
    FakeEvidenceProvider,
    _request_fixture,
)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    url = os.getenv('HRMIS_EVIDENCE_TEST_URL')
    if url:
        # Explicitly require a local disposable target for destructive fixtures.
        assert 'hrmis_evidence_test' in url and '127.0.0.1' in url
        schema = 'evidence_' + uuid4().hex
        admin_engine = create_engine(url)
        with admin_engine.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        monkeypatch.setattr(TestingConfig, 'SQLALCHEMY_DATABASE_URI', url)
        monkeypatch.setattr(TestingConfig, 'SQLALCHEMY_ENGINE_OPTIONS', {
            'connect_args': {'options': f'-c search_path={schema}'},
        }, raising=False)
    app = create_app('testing')
    app.config['UPLOAD_FOLDER'] = str(tmp_path / 'uploads')
    with app.app_context():
        db.create_all()
        seed_roles_permissions()
    yield app
    with app.app_context():
        db.session.remove()
        if url:
            db.engine.dispose()
            with admin_engine.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            admin_engine.dispose()
        else:
            db.drop_all()


@pytest.fixture()
def scheduled(app, monkeypatch):
    monkeypatch.setattr(worker, 'create_app', lambda: app)
    monkeypatch.setattr(worker, 'stopping', False)
    monkeypatch.setattr(worker.time, 'sleep', lambda _: pytest.fail('one-shot slept'))
    provider = FakeEvidenceProvider()
    monkeypatch.setattr(service, 'get_signature_provider', lambda _: provider)
    return provider


def test_one_job_then_duplicate_run(app, tenant, admin_user, tmp_path, scheduled):
    request_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    started = time.perf_counter()
    worker.run(once=True)
    print(f'one-job execution_seconds={time.perf_counter() - started:.4f}')
    worker.run(once=True)
    with app.app_context():
        row = db.session.get(SignatureRequest, request_id)
        assert row.evidence_status == 'verified'
        assert row.evidence_attempts == 1
        assert len(scheduled.downloaded) == 1
        assert SignatureArtifact.query.count() == 2
        assert SignatureEvent.query.filter_by(event_type='signature.evidence_verified').count() == 1


def test_multiple_jobs_continue_next_schedule(app, tenant, admin_user, tmp_path, scheduled):
    ids = [_request_fixture(app, tenant, admin_user, tmp_path)[0] for _ in range(11)]
    started = time.perf_counter()
    worker.run(once=True)
    print(f'ten-job execution_seconds={time.perf_counter() - started:.4f}')
    with app.app_context():
        assert SignatureRequest.query.filter_by(evidence_status='verified').count() == 10
        assert SignatureRequest.query.filter_by(evidence_status='pending').count() == 1
    worker.run(once=True)
    assert set(map(str, scheduled.downloaded)) == set(ids)
    assert len(scheduled.downloaded) == 11


def test_retrieval_failure_due_retry_and_exhaustion(
    app, tenant, admin_user, tmp_path, scheduled, monkeypatch,
):
    request_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    scheduled.not_ready = True
    worker.run(once=True)
    with app.app_context():
        row = db.session.get(SignatureRequest, request_id)
        assert row.evidence_status == 'retry_scheduled'
        due = row.evidence_next_attempt_at
        assert SignatureArtifact.query.count() == 0
    monkeypatch.setattr(service, 'utcnow', lambda: due - timedelta(microseconds=1))
    worker.run(once=True)
    assert len(scheduled.downloaded) == 1
    monkeypatch.setattr(service, 'utcnow', lambda: due + timedelta(seconds=300))
    scheduled.not_ready = False
    worker.run(once=True)
    with app.app_context():
        row = db.session.get(SignatureRequest, request_id)
        assert row.evidence_status == 'verified'
        assert row.evidence_attempts == 2
    second_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    scheduled.not_ready = True
    for attempt in range(3):
        monkeypatch.setattr(service, 'utcnow', lambda attempt=attempt: utcnow() + timedelta(hours=attempt + 1))
        worker.run(once=True)
    with app.app_context():
        row = db.session.get(SignatureRequest, second_id)
        assert row.evidence_status == 'failed'
        assert row.evidence_attempts == 3
        assert row.evidence_next_attempt_at is None


def test_fresh_lease_skipped_and_abandoned_lease_recovered(
    app, tenant, admin_user, tmp_path, scheduled, monkeypatch,
):
    request_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    with app.app_context():
        assert service.claim_signature_evidence_jobs() == [request_id]
        assert service.claim_signature_evidence_jobs() == []
        locked_at = db.session.get(SignatureRequest, request_id).evidence_locked_at
    monkeypatch.setattr(service, 'utcnow', lambda: locked_at + timedelta(seconds=901))
    worker.run(once=True)
    with app.app_context():
        row = db.session.get(SignatureRequest, request_id)
        assert row.evidence_status == 'verified'
        assert row.evidence_attempts == 2
    assert len(scheduled.downloaded) == 1


@pytest.mark.parametrize('expired', [False, True])
def test_overlapping_runner_cannot_reclaim_active_download(
    app, tenant, admin_user, tmp_path, scheduled, monkeypatch, expired,
):
    with app.app_context():
        if db.engine.dialect.name != 'postgresql':
            pytest.skip('Real PostgreSQL required for row locking')
    request_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    entered = threading.Event()
    release = threading.Event()
    errors = []
    original = scheduled.download_artifacts

    def slow_download(row):
        entered.set()
        assert release.wait(10)
        return original(row)

    monkeypatch.setattr(scheduled, 'download_artifacts', slow_download)

    def first():
        try:
            worker.run(once=True)
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=first)
    thread.start()
    try:
        assert entered.wait(10)
        if expired:
            future = utcnow() + timedelta(seconds=901)
            monkeypatch.setattr(service, 'utcnow', lambda: future)
        worker.run(once=True)
        assert scheduled.downloaded == []  # Second runner never entered provider.
    finally:
        release.set()
        thread.join(15)
    assert not thread.is_alive()
    assert errors == []
    assert len(scheduled.downloaded) == 1
    with app.app_context():
        assert db.session.get(SignatureRequest, request_id).evidence_attempts == 1
        assert SignatureArtifact.query.count() == 2
        assert SignatureEvent.query.filter_by(event_type='signature.evidence_verified').count() == 1


def test_failure_does_not_overwrite_reclaimed_attempt(
    app, tenant, admin_user, tmp_path, scheduled, monkeypatch,
):
    request_id, _ = _request_fixture(app, tenant, admin_user, tmp_path)
    scheduled.not_ready = True
    reclaimed = []
    with app.app_context():
        assert service.claim_signature_evidence_jobs() == [request_id]
        session_type = type(db.session())
        original_rollback = session_type.rollback
        future = utcnow() + timedelta(seconds=901)
        monkeypatch.setattr(service, 'utcnow', lambda: future)

        def rollback_then_reclaim(session):
            original_rollback(session)
            if not reclaimed:
                with app.app_context():
                    reclaimed.extend(service.claim_signature_evidence_jobs())

        monkeypatch.setattr(session_type, 'rollback', rollback_then_reclaim)
        result = service.process_signature_evidence(request_id)
        assert reclaimed == [request_id]
        assert result.evidence_status == 'processing'
        assert result.evidence_attempts == 2
        assert result.evidence_next_attempt_at is None
        assert SignatureEvent.query.filter_by(event_type='signature.evidence_retry_scheduled').count() == 0
        db.session.commit()
