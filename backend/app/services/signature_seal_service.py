import hashlib
import math
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models import SignatureArtifact, SignatureRequest, SignatureSeal
from app.models.base import utcnow
from app.utils.signature_evidence_storage import (
    save_signature_artifact,
)
from app.utils.signature_seal_storage import (
    delete_signature_seal_image,
    save_signature_seal_image,
)


SEAL_STATUS_NOT_REQUIRED = 'not_required'
SEAL_STATUS_AWAITING_SIGNATURES = 'awaiting_signatures'
SEAL_STATUS_PENDING = 'pending'
SEAL_STATUS_APPLIED = 'applied'

SEAL_STATUSES = frozenset({
    SEAL_STATUS_NOT_REQUIRED,
    SEAL_STATUS_AWAITING_SIGNATURES,
    SEAL_STATUS_PENDING,
    SEAL_STATUS_APPLIED,
})


class SignatureSealError(ValueError):
    pass


def initialize_seal_lifecycle(signature_request):
    """Normalize seal state without changing signing status."""
    if not signature_request.seal_required:
        signature_request.seal_status = (
            SEAL_STATUS_NOT_REQUIRED
        )
        signature_request.sealed_at = None
        signature_request.sealed_by_id = None
        return signature_request

    if signature_request.status == 'completed':
        if signature_request.seal_status != (
            SEAL_STATUS_APPLIED
        ):
            signature_request.seal_status = (
                SEAL_STATUS_PENDING
            )

        return signature_request

    signature_request.seal_status = (
        SEAL_STATUS_AWAITING_SIGNATURES
    )
    signature_request.sealed_at = None
    signature_request.sealed_by_id = None
    return signature_request


def seal_ready(signature_request):
    return (
        signature_request.seal_required
        and signature_request.status == 'completed'
        and signature_request.seal_status
        == SEAL_STATUS_PENDING
    )


def _lock_signature_request_for_seal(signature_request):
    locked_request = (
        SignatureRequest.query.filter_by(
            id=signature_request.id,
            tenant_id=signature_request.tenant_id,
        )
        .with_for_update()
        .one()
    )

    db.session.refresh(locked_request)
    return locked_request


def require_seal_ready(signature_request):
    if not signature_request.seal_required:
        raise SignatureSealError(
            'This signature request does not require '
            'a company seal.'
        )

    if signature_request.status != 'completed':
        raise SignatureSealError(
            'The company seal cannot be managed until '
            'all required signatories have completed '
            'signing.'
        )

    if (
        signature_request.seal_status
        == SEAL_STATUS_APPLIED
    ):
        raise SignatureSealError(
            'The company seal has already been applied '
            'and is immutable.'
        )

    if (
        signature_request.seal_status
        != SEAL_STATUS_PENDING
    ):
        raise SignatureSealError(
            'The company seal is not ready to be '
            'managed.'
        )

    return signature_request


def _finite_number(value, name):
    if isinstance(value, bool):
        raise SignatureSealError(
            f'{name} must be a number.'
        )

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SignatureSealError(
            f'{name} must be a number.'
        ) from exc

    if not math.isfinite(number):
        raise SignatureSealError(
            f'{name} must be finite.'
        )

    return number


def validate_seal_placement(
    *,
    page_number,
    x,
    y,
    width,
    height,
):
    if isinstance(page_number, bool):
        raise SignatureSealError(
            'page_number must be a positive integer.'
        )

    try:
        page = int(page_number)
        numeric_page = float(page_number)
    except (TypeError, ValueError) as exc:
        raise SignatureSealError(
            'page_number must be a positive integer.'
        ) from exc

    if (
        page < 1
        or numeric_page != page
    ):
        raise SignatureSealError(
            'page_number must be a positive integer.'
        )

    normalized_x = _finite_number(
        x,
        'x',
    )
    normalized_y = _finite_number(
        y,
        'y',
    )
    normalized_width = _finite_number(
        width,
        'width',
    )
    normalized_height = _finite_number(
        height,
        'height',
    )

    if not 0 <= normalized_x <= 1:
        raise SignatureSealError(
            'x must be between 0 and 1.'
        )

    if not 0 <= normalized_y <= 1:
        raise SignatureSealError(
            'y must be between 0 and 1.'
        )

    if not 0 < normalized_width <= 1:
        raise SignatureSealError(
            'width must be greater than 0 '
            'and no greater than 1.'
        )

    if not 0 < normalized_height <= 1:
        raise SignatureSealError(
            'height must be greater than 0 '
            'and no greater than 1.'
        )

    if normalized_x + normalized_width > 1:
        raise SignatureSealError(
            'The company seal exceeds the '
            'horizontal page boundary.'
        )

    if normalized_y + normalized_height > 1:
        raise SignatureSealError(
            'The company seal exceeds the '
            'vertical page boundary.'
        )

    return {
        'page_number': page,
        'x': normalized_x,
        'y': normalized_y,
        'width': normalized_width,
        'height': normalized_height,
    }


def signature_seal_image_content(signature_request):
    seal = SignatureSeal.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
    ).first()

    if seal is None:
        raise SignatureSealError(
            'No company seal image has been uploaded.'
        )

    try:
        content = Path(
            seal.image_file_path
        ).read_bytes()
    except OSError as exc:
        raise SignatureSealError(
            'The company seal image is unavailable.'
        ) from exc

    checksum = hashlib.sha256(
        content
    ).hexdigest()

    if checksum != seal.image_sha256:
        raise SignatureSealError(
            'The company seal image failed its integrity check.'
        )

    return {
        'content': content,
        'mime_type': seal.image_mime_type,
        'filename': seal.image_original_filename,
    }


def upload_signature_seal_image(
    signature_request,
    file,
    actor,
):
    signature_request = _lock_signature_request_for_seal(
        signature_request
    )

    require_seal_ready(
        signature_request
    )

    seal = SignatureSeal.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=(
            signature_request.id
        ),
    ).first()

    if seal and (
        seal.applied_at
        or seal.sealed_artifact_id
    ):
        raise SignatureSealError(
            'The applied company seal cannot '
            'be replaced.'
        )

    stored = save_signature_seal_image(
        file,
        tenant_id=signature_request.tenant_id,
        signature_request_id=(
            signature_request.id
        ),
    )

    now = utcnow()

    previous_path = (
        seal.image_file_path
        if seal
        else None
    )

    if seal is None:
        seal = SignatureSeal(
            tenant_id=signature_request.tenant_id,
            signature_request_id=(
                signature_request.id
            ),
            image_original_filename=(
                stored['original_filename']
            ),
            image_stored_filename=(
                stored['stored_filename']
            ),
            image_file_path=(
                stored['file_path']
            ),
            image_mime_type=(
                stored['mime_type']
            ),
            image_size_bytes=(
                stored['size_bytes']
            ),
            image_sha256=(
                stored['checksum_sha256']
            ),
            uploaded_by_id=actor.id,
            uploaded_at=now,
        )
        db.session.add(seal)

    else:
        seal.image_original_filename = (
            stored['original_filename']
        )
        seal.image_stored_filename = (
            stored['stored_filename']
        )
        seal.image_file_path = (
            stored['file_path']
        )
        seal.image_mime_type = (
            stored['mime_type']
        )
        seal.image_size_bytes = (
            stored['size_bytes']
        )
        seal.image_sha256 = (
            stored['checksum_sha256']
        )
        seal.uploaded_by_id = actor.id
        seal.uploaded_at = now

        # Replacing an image invalidates any
        # previous draft placement.
        seal.page_number = None
        seal.x = None
        seal.y = None
        seal.width = None
        seal.height = None

    try:
        db.session.flush()
    except Exception:
        delete_signature_seal_image(
            stored['file_path']
        )
        raise

    if (
        previous_path
        and previous_path
        != stored['file_path']
    ):
        delete_signature_seal_image(
            previous_path
        )

    return seal


def update_signature_seal_placement(
    signature_request,
    *,
    page_number,
    x,
    y,
    width,
    height,
):
    signature_request = _lock_signature_request_for_seal(
        signature_request
    )

    require_seal_ready(
        signature_request
    )

    seal = SignatureSeal.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=(
            signature_request.id
        ),
    ).first()

    if seal is None:
        raise SignatureSealError(
            'Upload the company seal image '
            'before placing it.'
        )

    if (
        seal.applied_at
        or seal.sealed_artifact_id
    ):
        raise SignatureSealError(
            'The applied company seal cannot '
            'be moved.'
        )

    placement = validate_seal_placement(
        page_number=page_number,
        x=x,
        y=y,
        width=width,
        height=height,
    )

    seal.page_number = (
        placement['page_number']
    )
    seal.x = placement['x']
    seal.y = placement['y']
    seal.width = placement['width']
    seal.height = placement['height']

    db.session.flush()

    return seal



def require_complete_seal_placement(seal):
    if seal is None:
        raise SignatureSealError(
            'Upload the company seal image before applying it.'
        )

    required = (
        seal.page_number,
        seal.x,
        seal.y,
        seal.width,
        seal.height,
    )

    if any(value is None for value in required):
        raise SignatureSealError(
            'Place the company seal on the signed document '
            'before applying it.'
        )

    return validate_seal_placement(
        page_number=seal.page_number,
        x=seal.x,
        y=seal.y,
        width=seal.width,
        height=seal.height,
    )


def render_company_seal_pdf(
    signed_pdf_bytes,
    seal_image_bytes,
    placement,
):
    if (
        not isinstance(signed_pdf_bytes, bytes)
        or not signed_pdf_bytes
    ):
        raise SignatureSealError(
            'The signed document is unavailable.'
        )

    if (
        not isinstance(seal_image_bytes, bytes)
        or not seal_image_bytes
    ):
        raise SignatureSealError(
            'The company seal image is unavailable.'
        )

    validated = validate_seal_placement(
        page_number=placement.get('page_number'),
        x=placement.get('x'),
        y=placement.get('y'),
        width=placement.get('width'),
        height=placement.get('height'),
    )

    try:
        reader = PdfReader(
            BytesIO(signed_pdf_bytes)
        )
    except Exception as exc:
        raise SignatureSealError(
            'Kinetic could not open the signed PDF '
            'for company sealing.'
        ) from exc

    if not reader.pages:
        raise SignatureSealError(
            'The signed PDF contains no pages.'
        )

    page_index = (
        validated['page_number'] - 1
    )

    if page_index >= len(reader.pages):
        raise SignatureSealError(
            'The selected company-seal page does not '
            'exist in the signed PDF.'
        )

    try:
        image = ImageReader(
            BytesIO(seal_image_bytes)
        )
    except Exception as exc:
        raise SignatureSealError(
            'Kinetic could not read the company seal image.'
        ) from exc

    writer = PdfWriter()

    for index, page in enumerate(reader.pages):
        if index == page_index:
            page_width = float(
                page.mediabox.width
            )
            page_height = float(
                page.mediabox.height
            )

            packet = BytesIO()
            overlay = canvas.Canvas(
                packet,
                pagesize=(
                    page_width,
                    page_height,
                ),
            )

            draw_x = (
                validated['x']
                * page_width
            )
            draw_width = (
                validated['width']
                * page_width
            )
            draw_height = (
                validated['height']
                * page_height
            )

            # Browser/PDF.js placement coordinates use
            # the page's top-left as the origin. PDF
            # coordinates use the bottom-left.
            draw_y = (
                page_height
                - (
                    validated['y']
                    + validated['height']
                )
                * page_height
            )

            overlay.drawImage(
                image,
                draw_x,
                draw_y,
                width=draw_width,
                height=draw_height,
                preserveAspectRatio=False,
                mask='auto',
            )
            overlay.save()

            packet.seek(0)

            try:
                overlay_page = PdfReader(
                    packet
                ).pages[0]
            except Exception as exc:
                raise SignatureSealError(
                    'Kinetic could not render the '
                    'company seal overlay.'
                ) from exc

            page.merge_page(
                overlay_page
            )

        writer.add_page(page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def apply_signature_seal(
    signature_request,
    actor,
):
    signature_request = _lock_signature_request_for_seal(
        signature_request
    )

    require_seal_ready(
        signature_request
    )

    seal = SignatureSeal.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
    ).first()

    placement = require_complete_seal_placement(
        seal
    )

    if (
        seal.applied_at
        or seal.sealed_artifact_id
    ):
        raise SignatureSealError(
            'The company seal has already been applied.'
        )

    existing_sealed = SignatureArtifact.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type='sealed_document',
    ).first()

    if existing_sealed:
        raise SignatureSealError(
            'A sealed document already exists for '
            'this signature request.'
        )

    signed_artifact = SignatureArtifact.query.filter_by(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type='signed_document',
    ).first()

    if signed_artifact is None:
        raise SignatureSealError(
            'The completed signed document is unavailable.'
        )

    # Import locally to avoid coupling the evidence service
    # into module initialization of the seal workflow.
    from app.services.signature_evidence_service import (
        artifact_content,
    )

    try:
        signed_pdf_bytes = artifact_content(signed_artifact)
    except Exception as exc:
        raise SignatureSealError(
            'The signed document failed integrity verification.'
        ) from exc

    image_path = Path(
        seal.image_file_path
    )

    if not image_path.is_file():
        raise SignatureSealError(
            'The uploaded company seal image is unavailable.'
        )

    seal_image_bytes = (
        image_path.read_bytes()
    )

    image_checksum = hashlib.sha256(
        seal_image_bytes
    ).hexdigest()

    if image_checksum != seal.image_sha256:
        raise SignatureSealError(
            'The company seal image failed integrity verification.'
        )

    sealed_pdf_bytes = render_company_seal_pdf(
        signed_pdf_bytes,
        seal_image_bytes,
        placement,
    )

    now = utcnow()

    signed_name = Path(
        signed_artifact.original_filename
    )

    if signed_name.stem.endswith(' - Signed'):
        base_name = signed_name.stem[
            :-len(' - Signed')
        ]
    else:
        base_name = signed_name.stem

    filename = (
        f'{base_name} - Sealed.pdf'
    )

    stored = save_signature_artifact(
        sealed_pdf_bytes,
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        filename=filename,
        mime_type='application/pdf',
    )

    sealed_artifact = SignatureArtifact(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type='sealed_document',
        provider='internal',
        original_filename=stored[
            'original_filename'
        ],
        stored_filename=stored[
            'stored_filename'
        ],
        file_path=stored['file_path'],
        mime_type='application/pdf',
        size_bytes=stored['size_bytes'],
        checksum_sha256=stored[
            'checksum_sha256'
        ],
        captured_at=now,
        metadata_json={
            'request_id': str(
                signature_request.id
            ),
            'source_signed_document_artifact_id': str(
                signed_artifact.id
            ),
            'source_signed_document_sha256':
                signed_artifact.checksum_sha256,
            'seal_id': str(seal.id),
            'seal_image_sha256':
                seal.image_sha256,
            'seal_page_number':
                placement['page_number'],
            'seal_x': placement['x'],
            'seal_y': placement['y'],
            'seal_width':
                placement['width'],
            'seal_height':
                placement['height'],
            'applied_by_id': str(
                actor.id
            ),
            'applied_at': now.isoformat(),
        },
    )

    db.session.add(
        sealed_artifact
    )
    db.session.flush()

    seal.sealed_artifact_id = sealed_artifact.id
    seal.applied_at = now
    seal.applied_by_id = actor.id

    signature_request.seal_status = SEAL_STATUS_APPLIED
    signature_request.sealed_at = now
    signature_request.sealed_by_id = actor.id

    from app.services.signature_service import (
        _record_event,
    )

    _record_event(
        signature_request,
        'signature.company_seal_applied',
        actor=actor,
        description=(
            'Company seal applied to the completed '
            'signed document'
        ),
        metadata={
            'seal_id': str(seal.id),
            'sealed_document_artifact_id': str(
                sealed_artifact.id
            ),
            'source_signed_document_artifact_id': str(
                signed_artifact.id
            ),
            'source_signed_document_sha256':
                signed_artifact.checksum_sha256,
            'sealed_document_sha256':
                sealed_artifact.checksum_sha256,
            'seal_image_sha256':
                seal.image_sha256,
            'page_number':
                placement['page_number'],
            'x': placement['x'],
            'y': placement['y'],
            'width': placement['width'],
            'height': placement['height'],
            'applied_at': now.isoformat(),
        },
    )

    db.session.flush()

    return sealed_artifact
