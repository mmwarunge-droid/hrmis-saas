from pathlib import Path
from types import SimpleNamespace

from app.services.signature_seal_service import (
    SEAL_STATUS_AWAITING_SIGNATURES,
    SEAL_STATUS_NOT_REQUIRED,
    SEAL_STATUS_PENDING,
    initialize_seal_lifecycle,
)


def _request(
    *,
    seal_required,
    status,
    seal_status='not_required',
):
    return SimpleNamespace(
        seal_required=seal_required,
        status=status,
        seal_status=seal_status,
        sealed_at=None,
        sealed_by_id=None,
    )


def test_required_seal_waits_while_signatures_are_incomplete():
    request = _request(
        seal_required=True,
        status='in_progress',
    )

    initialize_seal_lifecycle(request)

    assert request.seal_status == (
        SEAL_STATUS_AWAITING_SIGNATURES
    )


def test_required_seal_becomes_pending_after_signing_completes():
    request = _request(
        seal_required=True,
        status='completed',
        seal_status=SEAL_STATUS_AWAITING_SIGNATURES,
    )

    initialize_seal_lifecycle(request)

    assert request.seal_status == SEAL_STATUS_PENDING


def test_non_sealed_request_preserves_existing_completion_behavior():
    request = _request(
        seal_required=False,
        status='completed',
    )

    initialize_seal_lifecycle(request)

    assert request.seal_status == SEAL_STATUS_NOT_REQUIRED


def test_native_completion_path_advances_seal_lifecycle():
    source = Path(
        'app/services/signature_service.py'
    ).read_text()

    completion = source.index(
        "signature_request.status = 'completed'"
    )

    following = source[
        completion:
        completion + 500
    ]

    assert (
        'initialize_seal_lifecycle(signature_request)'
        in following
    )


def test_provider_completion_path_advances_seal_lifecycle():
    source = Path(
        'app/services/signature_evidence_service.py'
    ).read_text()

    completion = source.index(
        "signature_request.status = 'completed'"
    )

    following = source[
        completion:
        completion + 500
    ]

    assert (
        'initialize_seal_lifecycle(signature_request)'
        in following
    )
