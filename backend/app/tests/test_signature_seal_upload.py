import importlib
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from werkzeug.datastructures import FileStorage

from app.services import signature_seal_service


def _request(
    *,
    seal_required=True,
    status='completed',
    seal_status='pending',
):
    return SimpleNamespace(
        seal_required=seal_required,
        status=status,
        seal_status=seal_status,
    )


def _placement_validator():
    assert hasattr(
        signature_seal_service,
        'validate_seal_placement',
    )
    return signature_seal_service.validate_seal_placement


def _readiness_guard():
    assert hasattr(
        signature_seal_service,
        'require_seal_ready',
    )
    return signature_seal_service.require_seal_ready


def _storage_module():
    module_name = 'app.utils.signature_seal_storage'

    assert importlib.util.find_spec(module_name) is not None

    return importlib.import_module(module_name)


def test_seal_upload_requires_completed_pending_request():
    guard = _readiness_guard()

    guard(
        _request(
            seal_required=True,
            status='completed',
            seal_status='pending',
        )
    )

    invalid_requests = [
        _request(
            seal_required=False,
            status='completed',
            seal_status='pending',
        ),
        _request(
            seal_required=True,
            status='in_progress',
            seal_status='awaiting_signatures',
        ),
        _request(
            seal_required=True,
            status='completed',
            seal_status='awaiting_signatures',
        ),
        _request(
            seal_required=True,
            status='completed',
            seal_status='applied',
        ),
    ]

    for request in invalid_requests:
        with pytest.raises(
            signature_seal_service.SignatureSealError
        ):
            guard(request)


def test_seal_placement_accepts_normalized_pdf_coordinates():
    validate = _placement_validator()

    placement = validate(
        page_number=2,
        x=0.10,
        y=0.20,
        width=0.30,
        height=0.25,
    )

    assert placement == {
        'page_number': 2,
        'x': 0.10,
        'y': 0.20,
        'width': 0.30,
        'height': 0.25,
    }


@pytest.mark.parametrize(
    (
        'page_number',
        'x',
        'y',
        'width',
        'height',
    ),
    [
        (0, 0.1, 0.1, 0.2, 0.2),
        (1, -0.1, 0.1, 0.2, 0.2),
        (1, 0.1, -0.1, 0.2, 0.2),
        (1, 0.1, 0.1, 0.0, 0.2),
        (1, 0.1, 0.1, 0.2, 0.0),
        (1, 0.9, 0.1, 0.2, 0.2),
        (1, 0.1, 0.9, 0.2, 0.2),
        (1, 1.1, 0.1, 0.2, 0.2),
        (1, 0.1, 1.1, 0.2, 0.2),
    ],
)
def test_seal_placement_rejects_out_of_bounds_values(
    page_number,
    x,
    y,
    width,
    height,
):
    validate = _placement_validator()

    with pytest.raises(
        signature_seal_service.SignatureSealError
    ):
        validate(
            page_number=page_number,
            x=x,
            y=y,
            width=width,
            height=height,
        )


def test_seal_storage_accepts_png_and_returns_integrity_metadata(
    app,
    tmp_path,
):
    storage = _storage_module()

    app.config['UPLOAD_FOLDER'] = str(tmp_path)

    content = (
        b'\x89PNG\r\n\x1a\n'
        + b'company-seal'
    )

    file = FileStorage(
        stream=io.BytesIO(content),
        filename='company-seal.png',
        content_type='image/png',
    )

    with app.app_context():
        stored = storage.save_signature_seal_image(
            file,
            tenant_id=uuid4(),
            signature_request_id=uuid4(),
        )

    assert stored['original_filename'] == 'company-seal.png'
    assert stored['mime_type'] == 'image/png'
    assert stored['size_bytes'] == len(content)
    assert len(stored['checksum_sha256']) == 64

    stored_path = Path(stored['file_path'])
    assert stored_path.exists()
    assert stored_path.read_bytes() == content


@pytest.mark.parametrize(
    'content, filename',
    [
        (b'not-an-image', 'seal.png'),
        (b'', 'seal.png'),
    ],
)
def test_seal_storage_rejects_invalid_or_empty_content(
    app,
    tmp_path,
    content,
    filename,
):
    storage = _storage_module()

    app.config['UPLOAD_FOLDER'] = str(tmp_path)

    file = FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type='image/png',
    )

    with app.app_context():
        with pytest.raises(ValueError):
            storage.save_signature_seal_image(
                file,
                tenant_id=uuid4(),
                signature_request_id=uuid4(),
            )


def test_seal_management_routes_require_document_approve():
    source = Path(
        'app/routes/signature_routes.py'
    ).read_text()

    for route in (
        "@signature_bp.get('/<request_id>/seal/image')",
        "@signature_bp.post('/<request_id>/seal/image')",
        "@signature_bp.patch('/<request_id>/seal/placement')",
    ):
        assert route in source

        start = source.index(route)
        following = source[start:start + 500]

        assert '@jwt_required()' in following
        assert (
            "@permission_required('document:approve')"
            in following
        )


def test_unauthenticated_seal_upload_is_rejected(client):
    request_id = uuid4()

    response = client.post(
        f'/api/signature-requests/{request_id}/seal/image',
        data={
            'file': (
                io.BytesIO(
                    b'\x89PNG\r\n\x1a\nseal'
                ),
                'seal.png',
            ),
        },
        content_type='multipart/form-data',
    )

    assert response.status_code == 401


def test_unauthenticated_seal_image_download_is_rejected(client):
    request_id = uuid4()

    response = client.get(
        f'/api/signature-requests/{request_id}/seal/image',
    )

    assert response.status_code == 401


def test_unauthenticated_seal_placement_is_rejected(client):
    request_id = uuid4()

    response = client.patch(
        f'/api/signature-requests/{request_id}/seal/placement',
        json={
            'page_number': 1,
            'x': 0.1,
            'y': 0.1,
            'width': 0.2,
            'height': 0.2,
        },
    )

    assert response.status_code == 401
