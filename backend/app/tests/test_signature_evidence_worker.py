import logging
from types import SimpleNamespace

import pytest

import signature_evidence_worker as worker


@pytest.mark.parametrize('fails', [False, True])
def test_worker_reports_job_cost_through_configured_logger(
    app, monkeypatch, caplog, fails,
):
    monkeypatch.setattr(worker, 'create_app', lambda: app)
    monkeypatch.setattr(worker, 'stopping', False)
    monkeypatch.setattr(worker, 'claim_signature_evidence_jobs', lambda: ['job-id'])
    elapsed = iter([10.0, 12.5])
    cpu = iter([1.0, 1.25])
    monkeypatch.setattr(worker.time, 'perf_counter', lambda: next(elapsed))
    monkeypatch.setattr(worker.time, 'process_time', lambda: next(cpu))

    def process(request_id):
        assert request_id == 'job-id'
        if fails:
            raise RuntimeError('Simulated worker failure')
        return SimpleNamespace(evidence_status='verified')

    monkeypatch.setattr(worker, 'process_signature_evidence', process)
    app.logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger=app.name):
            if fails:
                with pytest.raises(RuntimeError, match='unhandled job failures'):
                    worker.run(once=True)
            else:
                worker.run(once=True)
    finally:
        app.logger.removeHandler(caplog.handler)
    messages = [record.getMessage() for record in caplog.records]
    assert any('duration_seconds=2.500 cpu_seconds=0.250' in m for m in messages)
    assert any(('crashed' if fails else 'status verified') in m for m in messages)


def test_empty_worker_batch_does_not_emit_job_metrics(app, monkeypatch, caplog):
    monkeypatch.setattr(worker, 'create_app', lambda: app)
    monkeypatch.setattr(worker, 'stopping', False)
    monkeypatch.setattr(worker, 'claim_signature_evidence_jobs', lambda: [])
    calls = []
    monkeypatch.setattr(worker, 'process_signature_evidence', calls.append)
    app.logger.addHandler(caplog.handler)
    try:
        with caplog.at_level(logging.INFO, logger=app.name):
            worker.run(once=True)
    finally:
        app.logger.removeHandler(caplog.handler)
    assert calls == []
    assert not any('Evidence job' in record.getMessage() for record in caplog.records)


def test_once_propagates_claim_failure(app, monkeypatch):
    monkeypatch.setattr(worker, 'create_app', lambda: app)
    monkeypatch.setattr(worker, 'stopping', False)

    def unavailable():
        raise RuntimeError('Database unavailable')

    monkeypatch.setattr(worker, 'claim_signature_evidence_jobs', unavailable)
    with pytest.raises(RuntimeError, match='Database unavailable'):
        worker.run(once=True)


def test_once_finishes_other_claims_before_reporting_crash(app, monkeypatch):
    monkeypatch.setattr(worker, 'create_app', lambda: app)
    monkeypatch.setattr(worker, 'stopping', False)
    monkeypatch.setattr(worker, 'claim_signature_evidence_jobs', lambda: ['bad', 'good'])
    processed = []

    def process(request_id):
        processed.append(request_id)
        if request_id == 'bad':
            raise RuntimeError('unexpected failure')
        return SimpleNamespace(evidence_status='verified')

    monkeypatch.setattr(worker, 'process_signature_evidence', process)
    with pytest.raises(RuntimeError, match='unhandled job failures'):
        worker.run(once=True)
    assert processed == ['bad', 'good']
