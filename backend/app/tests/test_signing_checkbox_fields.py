from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from marshmallow import ValidationError

from app.schemas.signature_schema import (
    SignatureFieldCreateSchema,
)
from app.services import native_signature_service
from app.services.native_signature_service import (
    NativeSignatureError,
    complete_recipient_fields,
)


def _payload(**changes):
    payload = {
        'field_type': 'checkbox',
        'label': 'Acknowledgement',
        'page_number': 1,
        'x': 0.10,
        'y': 0.20,
        'width': 0.05,
        'height': 0.04,
        'required': True,
    }
    payload.update(changes)
    return payload


def _field(
    *,
    mark_style='tick',
    required=True,
):
    return SimpleNamespace(
        id=uuid4(),
        field_type='checkbox',
        mark_style=mark_style,
        label='Acknowledgement',
        required=required,
        value=None,
        completed_at=None,
    )


def _recipient(*fields):
    return SimpleNamespace(
        name='Demo Signer',
        fields=list(fields),
    )


def test_checkbox_schema_supports_tick_cross_and_either():
    schema = SignatureFieldCreateSchema()

    for mark_style in (
        'tick',
        'cross',
        'either',
    ):
        result = schema.load(
            _payload(
                mark_style=mark_style,
            )
        )

        assert result['field_type'] == 'checkbox'
        assert result['mark_style'] == mark_style


def test_checkbox_schema_defaults_to_tick():
    result = SignatureFieldCreateSchema().load(
        _payload()
    )

    assert result['mark_style'] == 'tick'


def test_non_checkbox_field_rejects_mark_style():
    with pytest.raises(ValidationError):
        SignatureFieldCreateSchema().load(
            _payload(
                field_type='text',
                mark_style='tick',
            )
        )


def test_checkbox_submission_persists_allowed_marks():
    tick_field = _field(
        mark_style='tick',
    )
    either_field = _field(
        mark_style='either',
    )

    recipient = _recipient(
        tick_field,
        either_field,
    )

    signed_at = datetime(
        2026,
        9,
        3,
        5,
        0,
        0,
    )

    complete_recipient_fields(
        recipient,
        signed_at,
        'Demo Signer',
        field_values=[
            {
                'field_id': str(tick_field.id),
                'value': 'tick',
            },
            {
                'field_id': str(either_field.id),
                'value': ' Cross ',
            },
        ],
    )

    assert tick_field.value == 'tick'
    assert tick_field.completed_at == signed_at

    assert either_field.value == 'cross'
    assert either_field.completed_at == signed_at


@pytest.mark.parametrize(
    ('mark_style', 'submitted'),
    [
        ('tick', 'cross'),
        ('cross', 'tick'),
        ('either', 'yes'),
        ('either', 'checked'),
        ('either', '1'),
    ],
)
def test_checkbox_submission_rejects_invalid_marks(
    mark_style,
    submitted,
):
    checkbox = _field(
        mark_style=mark_style,
        required=False,
    )

    recipient = _recipient(
        checkbox,
    )

    with pytest.raises(
        NativeSignatureError,
        match='mark',
    ):
        complete_recipient_fields(
            recipient,
            datetime(
                2026,
                9,
                3,
                5,
                0,
                0,
            ),
            'Demo Signer',
            field_values=[
                {
                    'field_id': str(
                        checkbox.id
                    ),
                    'value': submitted,
                },
            ],
        )


def test_required_checkbox_must_be_marked():
    checkbox = _field(
        mark_style='tick',
        required=True,
    )

    with pytest.raises(
        NativeSignatureError,
        match='Required signing fields',
    ):
        complete_recipient_fields(
            _recipient(checkbox),
            datetime(
                2026,
                9,
                3,
                5,
                0,
                0,
            ),
            'Demo Signer',
            field_values=[],
        )



# MULTIPARTY-003-PDF-RED
class _MarkRecordingCanvas:
    def __init__(self):
        self.strings = []
        self.lines = []
        self.line_widths = []

    def setFont(self, *_args):
        return None

    def stringWidth(
        self,
        text,
        _font,
        font_size,
    ):
        return len(str(text)) * font_size * 0.5

    def drawString(self, x, y, text):
        self.strings.append(
            (x, y, str(text)),
        )

    def setLineWidth(self, value):
        self.line_widths.append(value)

    def line(self, x1, y1, x2, y2):
        self.lines.append(
            (x1, y1, x2, y2),
        )


@pytest.mark.parametrize(
    'mark',
    [
        'tick',
        'cross',
    ],
)
def test_checkbox_pdf_stamps_vector_mark_without_text(
    mark,
):
    pdf_canvas = _MarkRecordingCanvas()

    checkbox = SimpleNamespace(
        id=uuid4(),
        field_type='checkbox',
        mark_style='either',
        label='Acknowledgement',
        x=0.20,
        y=0.30,
        width=0.06,
        height=0.05,
        value=mark,
        recipient=None,
    )

    native_signature_service._draw_field(
        pdf_canvas,
        checkbox,
        612,
        792,
    )

    # The source PDF must contain only a professional mark
    # inside the configured rectangle. It must not receive
    # editor labels or the literal words "tick"/"cross".
    assert pdf_canvas.strings == []
    assert len(pdf_canvas.lines) == 2
