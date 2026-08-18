from io import BytesIO
from zipfile import ZipFile

import pytest

from app.services.document_conversion_service import (
    DocumentConversionError,
    convert_docx_to_pdf,
)


def test_macro_bearing_docx_is_rejected_before_conversion():
    buffer = BytesIO()

    with ZipFile(buffer, 'w') as archive:
        archive.writestr(
            '[Content_Types].xml',
            '<Types></Types>',
        )
        archive.writestr(
            'word/document.xml',
            '<document></document>',
        )
        archive.writestr(
            'word/vbaProject.bin',
            b'macro-content',
        )

    with pytest.raises(
        DocumentConversionError,
        match='Macro-enabled Word documents are not supported',
    ):
        convert_docx_to_pdf(buffer.getvalue())
