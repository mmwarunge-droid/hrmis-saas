from pathlib import Path
from types import SimpleNamespace

from app.schemas.signature_schema import (
    SignatureRequestCreateSchema,
)
from app.services.signature_seal_service import seal_ready


def _request(
    *,
    seal_required,
    status,
    seal_status,
):
    return SimpleNamespace(
        seal_required=seal_required,
        status=status,
        seal_status=seal_status,
    )


def test_create_schema_exposes_seal_required_default_false():
    field = SignatureRequestCreateSchema().fields[
        'seal_required'
    ]

    assert field.load_default is False
    assert field.deserialize(True) is True
    assert field.deserialize(False) is False


def test_create_service_persists_and_initializes_seal_requirement():
    source = Path(
        'app/services/signature_service.py'
    ).read_text()

    creation_start = source.index(
        'signature_request = SignatureRequest('
    )
    following = source[
        creation_start:
        creation_start + 1800
    ]

    assert (
        "seal_required=payload.get('seal_required', False)"
        in following
    )
    assert (
        'initialize_seal_lifecycle(signature_request)'
        in following
    )


def test_seal_readiness_requires_completed_pending_request():
    assert seal_ready(
        _request(
            seal_required=True,
            status='completed',
            seal_status='pending',
        )
    )

    assert not seal_ready(
        _request(
            seal_required=False,
            status='completed',
            seal_status='pending',
        )
    )

    assert not seal_ready(
        _request(
            seal_required=True,
            status='in_progress',
            seal_status='awaiting_signatures',
        )
    )

    assert not seal_ready(
        _request(
            seal_required=True,
            status='completed',
            seal_status='awaiting_signatures',
        )
    )

    assert not seal_ready(
        _request(
            seal_required=True,
            status='completed',
            seal_status='applied',
        )
    )
