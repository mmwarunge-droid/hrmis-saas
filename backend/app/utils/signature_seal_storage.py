from hashlib import sha256
from pathlib import Path
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


MAX_SIGNATURE_SEAL_IMAGE_BYTES = 5 * 1024 * 1024


def _detect_image_type(header: bytes):
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png', 'image/png'

    if header.startswith(b'\xff\xd8\xff'):
        return 'jpg', 'image/jpeg'

    if (
        len(header) >= 12
        and header[:4] == b'RIFF'
        and header[8:12] == b'WEBP'
    ):
        return 'webp', 'image/webp'

    return None


def _seal_root(
    tenant_id,
    signature_request_id,
) -> Path:
    return (
        Path(current_app.config['UPLOAD_FOLDER'])
        / str(tenant_id)
        / 'signature-seals'
        / str(signature_request_id)
    )


def save_signature_seal_image(
    file: FileStorage,
    *,
    tenant_id,
    signature_request_id,
):
    if not file or not file.filename:
        raise ValueError(
            'Choose a PNG, JPEG or WebP company seal image.'
        )

    header = file.stream.read(32)
    detected = _detect_image_type(header)

    if detected is None:
        raise ValueError(
            'Company seal images must be PNG, JPEG or WebP.'
        )

    extension, mime_type = detected
    file.stream.seek(0)

    folder = _seal_root(
        tenant_id,
        signature_request_id,
    )
    folder.mkdir(
        parents=True,
        exist_ok=True,
    )

    original_filename = secure_filename(
        file.filename
    )

    if not original_filename:
        original_filename = (
            f'company-seal.{extension}'
        )

    stored_filename = (
        f'seal-{uuid.uuid4().hex}.{extension}'
    )
    destination = folder / stored_filename

    written = 0
    digest = sha256()

    try:
        with destination.open('wb') as output:
            while True:
                chunk = file.stream.read(
                    64 * 1024
                )

                if not chunk:
                    break

                written += len(chunk)

                if (
                    written
                    > MAX_SIGNATURE_SEAL_IMAGE_BYTES
                ):
                    raise ValueError(
                        'Company seal images must be '
                        '5 MB or smaller.'
                    )

                digest.update(chunk)
                output.write(chunk)

    except Exception:
        destination.unlink(
            missing_ok=True
        )
        raise

    if written == 0:
        destination.unlink(
            missing_ok=True
        )
        raise ValueError(
            'The company seal image is empty.'
        )

    return {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'file_path': str(destination),
        'mime_type': mime_type,
        'size_bytes': written,
        'checksum_sha256': digest.hexdigest(),
    }


def delete_signature_seal_image(
    file_path,
):
    if not file_path:
        return

    try:
        Path(file_path).unlink(
            missing_ok=True
        )
    except OSError:
        return
