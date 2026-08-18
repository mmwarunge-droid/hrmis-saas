"""Server-side document conversion for Kinetic signing snapshots."""

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from zipfile import BadZipFile, ZipFile

from flask import current_app
from pypdf import PdfReader


DOCX_MIME_TYPE = (
    'application/vnd.openxmlformats-officedocument.'
    'wordprocessingml.document'
)


class DocumentConversionError(ValueError):
    """Raised when a document cannot be converted safely for signing."""


@dataclass(frozen=True)
class ConvertedPdf:
    content: bytes
    page_count: int
    engine: str
    engine_version: str | None = None


def is_docx_document(document):
    mime = (document.mime_type or '').lower().strip()
    filename = (document.original_filename or '').lower().strip()

    return mime == DOCX_MIME_TYPE or filename.endswith('.docx')


def _validate_docx(content):
    if not content:
        raise DocumentConversionError(
            'The Word document is empty.',
        )

    try:
        with ZipFile(BytesIO(content)) as archive:
            names = set(archive.namelist())

            if any(
                name.lower().endswith('vbaproject.bin')
                for name in names
            ):
                raise DocumentConversionError(
                    'Macro-enabled Word documents are not supported '
                    'for signing.',
                )
    except BadZipFile as exc:
        raise DocumentConversionError(
            'The signing source is not a valid DOCX document.',
        ) from exc

    required_parts = {
        '[Content_Types].xml',
        'word/document.xml',
    }

    if not required_parts.issubset(names):
        raise DocumentConversionError(
            'The signing source is not a valid Word DOCX document.',
        )


def _libreoffice_binary():
    configured = current_app.config.get(
        'LIBREOFFICE_BINARY',
        'libreoffice',
    )

    binary = shutil.which(configured)
    if not binary:
        raise DocumentConversionError(
            'Word document conversion is unavailable because '
            'LibreOffice is not installed.',
        )

    return binary


def _libreoffice_version(binary):
    try:
        result = subprocess.run(
            [binary, '--version'],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    if result.returncode != 0:
        return None

    output = (result.stdout or '').strip()
    return output.splitlines()[0] if output else None


def convert_docx_to_pdf(content):
    """Convert immutable DOCX bytes into a validated PDF snapshot."""

    _validate_docx(content)

    binary = _libreoffice_binary()
    timeout = int(
        current_app.config.get(
            'DOCX_CONVERSION_TIMEOUT_SECONDS',
            60,
        )
    )

    try:
        with tempfile.TemporaryDirectory(
            prefix='kinetic-docx-',
        ) as temp_directory:
            root = Path(temp_directory)
            source = root / 'source.docx'
            output_directory = root / 'output'
            profile_directory = root / 'libreoffice-profile'

            output_directory.mkdir()
            profile_directory.mkdir()

            source.write_bytes(content)

            profile_uri = profile_directory.resolve().as_uri()

            command = [
                binary,
                '--headless',
                '--nologo',
                '--nodefault',
                '--nolockcheck',
                '--nofirststartwizard',
                f'-env:UserInstallation={profile_uri}',
                '--convert-to',
                'pdf:writer_pdf_Export',
                '--outdir',
                str(output_directory),
                str(source),
            ]

            environment = os.environ.copy()
            environment['HOME'] = str(root)

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                check=False,
                env=environment,
            )

            converted = output_directory / 'source.pdf'

            if result.returncode != 0 or not converted.is_file():
                diagnostic = (
                    result.stderr
                    or result.stdout
                    or 'No conversion output was produced.'
                ).strip()

                raise DocumentConversionError(
                    'Kinetic could not convert the Word document '
                    f'to PDF. {diagnostic[:300]}'
                )

            pdf_content = converted.read_bytes()

    except subprocess.TimeoutExpired as exc:
        raise DocumentConversionError(
            'Word document conversion exceeded the allowed time.',
        ) from exc
    except OSError as exc:
        raise DocumentConversionError(
            'Kinetic could not start the Word conversion service.',
        ) from exc

    if not pdf_content.startswith(b'%PDF-'):
        raise DocumentConversionError(
            'Word conversion did not produce a valid PDF document.',
        )

    try:
        reader = PdfReader(BytesIO(pdf_content))
        page_count = len(reader.pages)
    except Exception as exc:
        raise DocumentConversionError(
            'Kinetic could not validate the converted PDF.',
        ) from exc

    if page_count < 1:
        raise DocumentConversionError(
            'The converted PDF contains no pages.',
        )

    return ConvertedPdf(
        content=pdf_content,
        page_count=page_count,
        engine='libreoffice',
        engine_version=_libreoffice_version(binary),
    )
