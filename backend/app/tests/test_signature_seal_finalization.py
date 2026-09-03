import base64
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from app.services import signature_seal_service


_TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB'
    'CAQAAAC1HAwCAAAAC0lEQVR42mNk+A8A'
    'AQUBAScY42YAAAAASUVORK5CYII='
)


def _pdf_bytes(page_count=2):
    output = BytesIO()
    pdf = canvas.Canvas(output)

    for page_number in range(1, page_count + 1):
        pdf.drawString(
            72,
            720,
            f'Contract page {page_number}',
        )
        pdf.showPage()

    pdf.save()
    return output.getvalue()


def _image_xobject_count(page):
    resources = page.get('/Resources')

    if not resources:
        return 0

    xobjects = resources.get('/XObject')

    if not xobjects:
        return 0

    count = 0

    for reference in xobjects.values():
        obj = reference.get_object()

        if obj.get('/Subtype') == '/Image':
            count += 1

    return count


def _renderer():
    assert hasattr(
        signature_seal_service,
        'render_company_seal_pdf',
    )

    return signature_seal_service.render_company_seal_pdf


def _placement_guard():
    assert hasattr(
        signature_seal_service,
        'require_complete_seal_placement',
    )

    return (
        signature_seal_service
        .require_complete_seal_placement
    )


def test_complete_seal_placement_is_required_before_apply():
    guard = _placement_guard()

    complete = SimpleNamespace(
        page_number=2,
        x=0.10,
        y=0.20,
        width=0.25,
        height=0.15,
    )

    assert guard(complete) == {
        'page_number': 2,
        'x': 0.10,
        'y': 0.20,
        'width': 0.25,
        'height': 0.15,
    }

    for missing in (
        'page_number',
        'x',
        'y',
        'width',
        'height',
    ):
        values = {
            'page_number': 1,
            'x': 0.10,
            'y': 0.20,
            'width': 0.25,
            'height': 0.15,
        }
        values[missing] = None

        seal = SimpleNamespace(**values)

        with pytest.raises(
            signature_seal_service.SignatureSealError
        ):
            guard(seal)


def test_renderer_composites_seal_on_selected_pdf_page():
    render = _renderer()

    result = render(
        _pdf_bytes(page_count=2),
        _TINY_PNG,
        {
            'page_number': 2,
            'x': 0.10,
            'y': 0.20,
            'width': 0.25,
            'height': 0.15,
        },
    )

    assert result.startswith(b'%PDF')

    reader = PdfReader(BytesIO(result))

    assert len(reader.pages) == 2
    assert _image_xobject_count(
        reader.pages[0]
    ) == 0
    assert _image_xobject_count(
        reader.pages[1]
    ) >= 1


def test_renderer_rejects_page_outside_signed_pdf():
    render = _renderer()

    with pytest.raises(
        signature_seal_service.SignatureSealError
    ):
        render(
            _pdf_bytes(page_count=1),
            _TINY_PNG,
            {
                'page_number': 2,
                'x': 0.10,
                'y': 0.20,
                'width': 0.25,
                'height': 0.15,
            },
        )


def test_finalization_service_contract_uses_signed_artifact():
    source = Path(
        'app/services/signature_seal_service.py'
    ).read_text()

    assert 'def apply_signature_seal(' in source

    required_fragments = (
        "artifact_type='signed_document'",
        "artifact_type='sealed_document'",
        'artifact_content(signed_artifact)',
        'save_signature_artifact(',
        "'source_signed_document_sha256':",
        "'seal_image_sha256':",
        'seal.sealed_artifact_id = sealed_artifact.id',
        'seal.applied_at = now',
        (
            'signature_request.seal_status = '
            'SEAL_STATUS_APPLIED'
        ),
        'signature_request.sealed_at = now',
        'signature_request.sealed_by_id = actor.id',
        "'signature.company_seal_applied'",
    )

    for fragment in required_fragments:
        assert fragment in source


def test_apply_route_requires_document_approve():
    source = Path(
        'app/routes/signature_routes.py'
    ).read_text()

    route = (
        "@signature_bp.post("
        "'/<request_id>/seal/apply'"
        ")"
    )

    assert route in source

    start = source.index(route)
    following = source[start:start + 700]

    assert '@jwt_required()' in following
    assert (
        "@permission_required('document:approve')"
        in following
    )
    assert 'apply_signature_seal(' in following


def test_unauthenticated_seal_apply_is_rejected(client):
    response = client.post(
        (
            '/api/signature-requests/'
            f'{uuid4()}/seal/apply'
        ),
    )

    assert response.status_code == 401


def test_finalization_does_not_rerender_unsigned_source():
    source = Path(
        'app/services/signature_seal_service.py'
    ).read_text()

    apply_start = source.find(
        'def apply_signature_seal('
    )

    assert apply_start >= 0

    apply_source = source[apply_start:]

    assert 'render_signature_pdf(' not in apply_source
    assert 'original_document' not in apply_source
