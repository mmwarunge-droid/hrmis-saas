"""Native Kinetic PDF signing support.

This module deliberately implements a focused PDF signing engine rather than a
full document editor. It owns recipient field placement, server-generated
signature text, PDF overlays and immutable signed-document artifacts.
"""

from functools import lru_cache
from io import BytesIO
from pathlib import Path

from flask import current_app
from pypdf import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import EmbeddedType1Face, Font
from reportlab.pdfgen import canvas

from app.extensions import db
from app.models import SignatureArtifact, SignatureField
from app.models.base import utcnow
from app.utils.signature_evidence_storage import (
    read_signature_artifact,
    save_signature_artifact,
)


DEFAULT_SIGNATURE_STYLE = 'calligraphy_1'
CONSENT_VERSION = 'kinetic-esign-v1'

HANDWRITTEN_FONT_NAME = 'KineticHandwritten'
HANDWRITTEN_FONT_FILES = (
    (
        Path(
            '/usr/share/fonts/type1/urw-base35/'
            'Z003-MediumItalic.afm'
        ),
        Path(
            '/usr/share/fonts/X11/Type1/'
            'Z003-MediumItalic.pfb'
        ),
    ),
)


class NativeSignatureError(ValueError):
    pass


def is_pdf_document(document):
    mime = (document.mime_type or '').lower()
    filename = (document.original_filename or '').lower()
    return mime == 'application/pdf' or filename.endswith('.pdf')


def canonical_signature_text(recipient, actor=None):
    """Generate the signature from the official employee/user identity."""
    employee = recipient.employee
    user = recipient.user
    actor_matches = bool(
        actor
        and str(getattr(actor, 'id', '')) == str(recipient.user_id)
    )
    first_name = (
        getattr(employee, 'first_name', None)
        or getattr(user, 'first_name', None)
        or (getattr(actor, 'first_name', None) if actor_matches else None)
        or ''
    ).strip()
    last_name = (
        getattr(employee, 'last_name', None)
        or getattr(user, 'last_name', None)
        or (getattr(actor, 'last_name', None) if actor_matches else None)
        or ''
    ).strip()

    if first_name and last_name:
        return f'{first_name[0].upper()}.{last_name}'
    if last_name:
        return last_name
    if first_name:
        return first_name

    fallback = (recipient.name or '').strip()
    if not fallback:
        raise NativeSignatureError(
            'The signatory does not have an official name on file.',
        )

    parts = fallback.split()
    if len(parts) >= 2:
        return f'{parts[0][0].upper()}.{" ".join(parts[1:])}'
    return fallback


def _source_artifact(signature_request):
    return SignatureArtifact.query.filter_by(
        signature_request_id=signature_request.id,
        artifact_type='original_document',
    ).first()


def source_pdf_bytes(signature_request):
    artifact = _source_artifact(signature_request)
    if artifact:
        content = read_signature_artifact(artifact.file_path)
    else:
        path = Path(signature_request.document.file_path)
        if not path.is_file():
            raise NativeSignatureError(
                'The source PDF is unavailable for signing.',
            )
        content = path.read_bytes()

    if not content.startswith(b'%PDF-'):
        raise NativeSignatureError(
            'The signing source is not a valid PDF document.',
        )
    return content


def source_page_count(signature_request):
    try:
        return len(PdfReader(BytesIO(source_pdf_bytes(signature_request))).pages)
    except NativeSignatureError:
        if current_app.config.get('TESTING'):
            return 1
        raise
    except Exception as exc:
        raise NativeSignatureError(
            'Kinetic could not read the PDF page structure.',
        ) from exc


def _default_field_specs(recipient_index, source_page_count_value):
    """Place signers on supplemental signing-record pages.

    Each page holds up to eight signatories in a two-column/four-row grid.
    This keeps the default mode usable for the request schema's larger signer
    counts instead of squeezing every recipient onto one page.
    """
    columns = 2
    rows_per_page = 4
    recipients_per_page = columns * rows_per_page
    page_offset = recipient_index // recipients_per_page
    slot = recipient_index % recipients_per_page
    column = slot % columns
    row = slot // columns

    x = 0.08 if column == 0 else 0.55
    width = 0.37
    block_top = 0.25 + (row * 0.145)
    page_number = source_page_count_value + 1 + page_offset

    return [
        {
            'field_type': 'signature',
            'label': 'Electronic signature',
            'page_number': page_number,
            'x': x,
            'y': block_top + 0.08,
            'width': width,
            'height': 0.06,
            'required': True,
        },
        {
            'field_type': 'date',
            'label': 'Date signed',
            'page_number': page_number,
            'x': x,
            'y': block_top + 0.15,
            'width': width,
            'height': 0.045,
            'required': True,
        },
    ]


def create_signature_fields(signature_request, recipient_fields=None):
    """Create recipient-owned signature/date fields for a new request.

    ``recipient_fields`` maps recipient IDs to custom field definitions. When a
    recipient has no custom definitions, Kinetic appends a dedicated signing
    record page and places recipients in a two-column layout.
    """
    if signature_request.fields:
        return list(signature_request.fields)

    recipients = list(signature_request.recipients)
    field_map = recipient_fields or {}
    source_pages = source_page_count(signature_request)
    created = []

    for index, recipient in enumerate(recipients):
        custom_specs = field_map.get(str(recipient.id)) or []
        specs = custom_specs or _default_field_specs(
            index,
            source_pages,
        )

        field_types = {item.get('field_type') for item in specs}
        if not {'signature', 'date'}.issubset(field_types):
            raise NativeSignatureError(
                f'{recipient.name} requires both a signature and date field.',
            )

        for spec in specs:
            page_number = int(spec['page_number'])
            x = float(spec['x'])
            y = float(spec['y'])
            width = float(spec['width'])
            height = float(spec['height'])

            if custom_specs and page_number > source_pages:
                raise NativeSignatureError(
                    f'{recipient.name} has a signing field outside the source PDF.',
                )
            if x < 0 or y < 0 or width <= 0 or height <= 0:
                raise NativeSignatureError('Signing field coordinates are invalid.')
            if x + width > 1 or y + height > 1:
                raise NativeSignatureError(
                    'A signing field extends beyond the PDF page boundary.',
                )

            field = SignatureField(
                tenant_id=signature_request.tenant_id,
                signature_request_id=signature_request.id,
                recipient_id=recipient.id,
                field_type=spec['field_type'],
                label=spec.get('label'),
                placeholder=spec.get('placeholder'),
                prefill_key=spec.get('prefill_key'),
                page_number=page_number,
                x=x,
                y=y,
                width=width,
                height=height,
                required=bool(spec.get('required', True)),
            )
            db.session.add(field)
            created.append(field)

    db.session.flush()
    return created


def complete_recipient_fields(
    recipient,
    signed_at,
    signature_text,
    field_values=None,
):
    if not recipient.fields:
        raise NativeSignatureError(
            'No signing fields are configured for this signatory.',
        )

    submitted = {}

    for item in field_values or []:
        field_id = str(item.get('field_id'))

        if field_id in submitted:
            raise NativeSignatureError(
                'A signing field was submitted more than once.',
            )

        submitted[field_id] = item.get('value')

    owned_fields = {
        str(field.id): field
        for field in recipient.fields
    }

    if set(submitted) - set(owned_fields):
        raise NativeSignatureError(
            'One or more submitted signing fields do not belong '
            'to this signatory.',
        )

    server_controlled = {
        'signature',
        'date',
        'name',
    }

    for field_id in submitted:
        field = owned_fields[field_id]

        if field.field_type in server_controlled:
            raise NativeSignatureError(
                f'{field.field_type.title()} fields are '
                'server-controlled and cannot be overridden.',
            )

    for field in recipient.fields:
        field_id = str(field.id)

        if field.field_type == 'signature':
            field.value = signature_text

        elif field.field_type == 'date':
            field.value = signed_at.strftime(
                '%d %b %Y'
            )

        elif field.field_type == 'name':
            field.value = recipient.name

        elif field.field_type in {
            'text',
            'initials',
        }:
            if field_id in submitted:
                raw_value = submitted[field_id]

                value = (
                    str(raw_value).strip()
                    if raw_value is not None
                    else ''
                )

                if (
                    field.field_type == 'initials'
                    and len(value) > 32
                ):
                    raise NativeSignatureError(
                        'Initials must not exceed 32 characters.',
                    )

                field.value = value or None

        if field.value:
            field.completed_at = signed_at

    missing = [
        field.label or field.field_type
        for field in recipient.fields
        if field.required and not field.value
    ]

    if missing:
        raise NativeSignatureError(
            'Required signing fields were not completed: '
            + ', '.join(missing),
        )


def _page_dimensions(page):
    return float(page.mediabox.width), float(page.mediabox.height)


def _field_baseline(field, page_height, font_size):
    top = field.y * page_height
    height = field.height * page_height
    return page_height - top - min(height * 0.72, font_size * 1.05)


def _draw_signing_record_header(pdf_canvas, signature_request, width, height):
    pdf_canvas.setFont('Helvetica-Bold', 18)
    pdf_canvas.drawString(
        width * 0.08,
        height * 0.90,
        'Kinetic Electronic Signing Record',
    )
    pdf_canvas.setFont('Helvetica', 10)
    pdf_canvas.drawString(
        width * 0.08,
        height * 0.865,
        signature_request.document.title[:95],
    )
    pdf_canvas.setFont('Helvetica', 8)
    pdf_canvas.drawString(
        width * 0.08,
        height * 0.835,
        f'Request ID: {signature_request.id}',
    )
    pdf_canvas.line(
        width * 0.08,
        height * 0.815,
        width * 0.92,
        height * 0.815,
    )


@lru_cache(maxsize=1)
def _handwritten_font_name():
    """Register the server-side handwritten signature font once.

    Debian's URW Z003 is a Chancery-style Type 1 face. ReportLab cannot
    register its CFF/OpenType file through TTFont, so the AFM/PFB pair is
    intentionally used here.
    """
    for afm_path, pfb_path in HANDWRITTEN_FONT_FILES:
        if not afm_path.is_file() or not pfb_path.is_file():
            continue

        try:
            face = EmbeddedType1Face(
                str(afm_path),
                str(pfb_path),
            )
            pdfmetrics.registerTypeFace(face)

            try:
                pdfmetrics.getFont(HANDWRITTEN_FONT_NAME)
            except KeyError:
                pdfmetrics.registerFont(
                    Font(
                        HANDWRITTEN_FONT_NAME,
                        face.name,
                        face.requiredEncoding
                        or 'WinAnsiEncoding',
                    )
                )

            return HANDWRITTEN_FONT_NAME
        except Exception:
            # Signing must remain available if an incorrectly built
            # environment is missing or cannot load the optional face.
            # Production Docker installs fonts-urw-base35 below.
            continue

    return 'Helvetica-Oblique'


def _signature_font(field):
    style = getattr(
        field.recipient,
        'signature_style',
        None,
    )

    if style == 'calligraphy_2':
        return _handwritten_font_name()

    return 'Times-Italic'


def _draw_field(pdf_canvas, field, page_width, page_height):
    if not field.value:
        return

    x = field.x * page_width
    y_top = page_height - (field.y * page_height)
    field_width = field.width * page_width
    field_height = field.height * page_height

    label = field.label or (
        'Electronic signature'
        if field.field_type == 'signature'
        else 'Date signed'
    )
    pdf_canvas.setFont('Helvetica', 7)
    pdf_canvas.drawString(x, y_top + 4, label)

    if field.field_type == 'signature':
        font_size = max(15, min(28, field_height * 0.55))
        pdf_canvas.setFont(_signature_font(field), font_size)
    else:
        font_size = max(9, min(12, field_height * 0.45))
        pdf_canvas.setFont('Helvetica', font_size)

    baseline = _field_baseline(field, page_height, font_size)
    text = str(field.value)
    # Avoid overflowing a recipient block. ReportLab's standard fonts do not
    # provide automatic wrapping for signatures, so trim very long names.
    while len(text) > 2 and pdf_canvas.stringWidth(
        text,
        _signature_font(field) if field.field_type == 'signature' else 'Helvetica',
        font_size,
    ) > field_width:
        text = text[:-1]
    if text != str(field.value):
        text = text.rstrip() + '...'

    pdf_canvas.drawString(x, baseline, text)
    pdf_canvas.setLineWidth(0.5)
    pdf_canvas.line(x, baseline - 4, x + field_width, baseline - 4)


def _draw_recipient_identity(pdf_canvas, recipient, signature_field, width, height):
    x = signature_field.x * width
    top = height - ((signature_field.y - 0.075) * height)
    pdf_canvas.setFont('Helvetica-Bold', 10)
    pdf_canvas.drawString(x, top, recipient.name[:55])
    pdf_canvas.setFont('Helvetica', 8)
    pdf_canvas.drawString(
        x,
        top - 13,
        (recipient.role_label or 'Signatory')[:60],
    )


def render_signature_pdf(signature_request):
    try:
        reader = PdfReader(BytesIO(source_pdf_bytes(signature_request)))
    except NativeSignatureError:
        raise
    except Exception as exc:
        raise NativeSignatureError(
            'Kinetic could not open the source PDF for signing.',
        ) from exc

    writer = PdfWriter()
    for page in reader.pages:
        # Normalize page rotation into the content stream before stamping.
        # PDF.js presents the rotated viewport to the field-placement UI;
        # this keeps normalized top-left coordinates aligned server-side.
        if page.rotation:
            page.transfer_rotation_to_content()
        writer.add_page(page)

    if not writer.pages:
        raise NativeSignatureError('The source PDF contains no pages.')

    max_page = max(
        [field.page_number for field in signature_request.fields]
        or [len(writer.pages)]
    )
    base_width, base_height = _page_dimensions(writer.pages[-1])
    while len(writer.pages) < max_page:
        writer.add_blank_page(width=base_width, height=base_height)

    source_page_count_value = len(reader.pages)

    for page_index, page in enumerate(writer.pages, start=1):
        page_fields = [
            field
            for field in signature_request.fields
            if field.page_number == page_index and field.value
        ]
        supplemental = page_index > source_page_count_value
        if not page_fields and not supplemental:
            continue

        page_width, page_height = _page_dimensions(page)
        packet = BytesIO()
        overlay = canvas.Canvas(packet, pagesize=(page_width, page_height))

        if supplemental:
            _draw_signing_record_header(
                overlay,
                signature_request,
                page_width,
                page_height,
            )
            for recipient in signature_request.recipients:
                signature_field = next((
                    field
                    for field in recipient.fields
                    if field.page_number == page_index
                    and field.field_type == 'signature'
                ), None)
                if signature_field:
                    _draw_recipient_identity(
                        overlay,
                        recipient,
                        signature_field,
                        page_width,
                        page_height,
                    )

        for field in page_fields:
            _draw_field(overlay, field, page_width, page_height)

        if supplemental:
            overlay.setFont('Helvetica', 7)
            overlay.drawString(
                page_width * 0.08,
                page_height * 0.05,
                'Signed electronically in Kinetic. Server timestamps are retained '
                'in the audit history.',
            )

        overlay.save()
        packet.seek(0)
        overlay_page = PdfReader(packet).pages[0]
        page.merge_page(overlay_page)

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def create_signed_document_artifact(signature_request):
    existing = SignatureArtifact.query.filter_by(
        signature_request_id=signature_request.id,
        artifact_type='signed_document',
    ).first()
    if existing:
        return existing

    content = render_signature_pdf(signature_request)
    source_artifact = _source_artifact(signature_request)
    original = Path(signature_request.document.original_filename)
    filename = f'{original.stem} - Signed.pdf'
    stored = save_signature_artifact(
        content,
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        filename=filename,
        mime_type='application/pdf',
    )
    now = utcnow()
    artifact = SignatureArtifact(
        tenant_id=signature_request.tenant_id,
        signature_request_id=signature_request.id,
        artifact_type='signed_document',
        provider='internal',
        original_filename=stored['original_filename'],
        stored_filename=stored['stored_filename'],
        file_path=stored['file_path'],
        mime_type='application/pdf',
        size_bytes=stored['size_bytes'],
        checksum_sha256=stored['checksum_sha256'],
        captured_at=now,
        metadata_json={
            'signature_method': 'kinetic_standard',
            'signer_count': len(signature_request.recipients),
            'source_document_sha256': (
                source_artifact.checksum_sha256
                if source_artifact
                else signature_request.document.checksum_sha256
            ),
            'generated_at': now.isoformat(),
            'request_id': str(signature_request.id),
        },
    )
    db.session.add(artifact)
    db.session.flush()
    return artifact
