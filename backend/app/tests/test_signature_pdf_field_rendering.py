from types import SimpleNamespace

from app.services.native_signature_service import _draw_field


PAGE_WIDTH = 612.0
PAGE_HEIGHT = 792.0


class RecordingCanvas:
    def __init__(self):
        self.fonts = []
        self.strings = []
        self.lines = []
        self.line_widths = []

    def setFont(self, name, size):
        self.fonts.append((name, float(size)))

    def drawString(self, x, y, text):
        self.strings.append(
            (float(x), float(y), str(text)),
        )

    def stringWidth(self, text, _font_name, font_size):
        # Deterministic approximation is sufficient for
        # testing the renderer's bounding behaviour.
        return len(str(text)) * float(font_size) * 0.55

    def setLineWidth(self, width):
        self.line_widths.append(float(width))

    def line(self, x1, y1, x2, y2):
        self.lines.append((
            float(x1),
            float(y1),
            float(x2),
            float(y2),
        ))


def field(
    *,
    field_type='signature',
    value='Mark Warunge',
    label='Electronic signature',
    x=0.20,
    y=0.40,
    width=0.30,
    height=0.04,
):
    return SimpleNamespace(
        field_type=field_type,
        value=value,
        label=label,
        x=x,
        y=y,
        width=width,
        height=height,
        recipient=SimpleNamespace(
            signature_style='calligraphy_1',
        ),
    )


def test_original_pdf_field_stamps_only_the_value():
    pdf_canvas = RecordingCanvas()
    signature_field = field()

    _draw_field(
        pdf_canvas,
        signature_field,
        PAGE_WIDTH,
        PAGE_HEIGHT,
    )

    rendered_strings = [
        item[2]
        for item in pdf_canvas.strings
    ]

    assert rendered_strings == ['Mark Warunge']
    assert pdf_canvas.lines == []


def test_original_pdf_signature_font_fits_field_height():
    pdf_canvas = RecordingCanvas()
    signature_field = field(
        height=0.025,
    )

    _draw_field(
        pdf_canvas,
        signature_field,
        PAGE_WIDTH,
        PAGE_HEIGHT,
    )

    value_font_size = pdf_canvas.fonts[-1][1]
    field_height = (
        signature_field.height
        * PAGE_HEIGHT
    )

    assert value_font_size <= (
        field_height * 0.62
        + 0.01
    )


def test_original_pdf_text_is_kept_inside_field_width():
    pdf_canvas = RecordingCanvas()
    text_field = field(
        field_type='text',
        value=(
            'A very long employee supplied value '
            'that cannot fit inside a narrow field'
        ),
        label='Work location',
        width=0.12,
        height=0.035,
    )

    _draw_field(
        pdf_canvas,
        text_field,
        PAGE_WIDTH,
        PAGE_HEIGHT,
    )

    assert len(pdf_canvas.strings) == 1

    rendered = pdf_canvas.strings[0][2]
    font_name, font_size = pdf_canvas.fonts[-1]

    available_width = (
        text_field.width
        * PAGE_WIDTH
        - 4.0
    )

    assert pdf_canvas.stringWidth(
        rendered,
        font_name,
        font_size,
    ) <= available_width + 0.01


def test_supplemental_record_retains_field_decoration():
    pdf_canvas = RecordingCanvas()
    signature_field = field()

    _draw_field(
        pdf_canvas,
        signature_field,
        PAGE_WIDTH,
        PAGE_HEIGHT,
        supplemental=True,
    )

    rendered_strings = [
        item[2]
        for item in pdf_canvas.strings
    ]

    assert rendered_strings == [
        'Electronic signature',
        'Mark Warunge',
    ]
    assert len(pdf_canvas.lines) == 1
