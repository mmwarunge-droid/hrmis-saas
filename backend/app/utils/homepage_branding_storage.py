from pathlib import Path
import uuid

from flask import current_app
from werkzeug.datastructures import FileStorage


MAX_BRANDING_IMAGE_BYTES = 5 * 1024 * 1024


def _detect_extension(header: bytes) -> str | None:
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if len(header) >= 12 and header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return 'webp'
    return None


def _asset_root(tenant_id) -> Path:
    return (
        Path(current_app.config['UPLOAD_FOLDER'])
        / str(tenant_id)
        / 'employee-homepage'
    )


def save_homepage_branding_image(
    file: FileStorage,
    tenant_id,
    asset: str,
) -> str:
    if asset not in {'banner', 'logo'}:
        raise ValueError('Unsupported branding asset')
    if not file or not file.filename:
        raise ValueError('Choose a PNG, JPEG or WebP image')

    header = file.stream.read(32)
    extension = _detect_extension(header)
    if extension is None:
        raise ValueError('Branding images must be PNG, JPEG or WebP')
    file.stream.seek(0)

    folder = _asset_root(tenant_id)
    folder.mkdir(parents=True, exist_ok=True)
    filename = f'{asset}-{uuid.uuid4().hex}.{extension}'
    destination = folder / filename

    written = 0
    try:
        with destination.open('wb') as output:
            while True:
                chunk = file.stream.read(64 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_BRANDING_IMAGE_BYTES:
                    raise ValueError('Branding images must be 5 MB or smaller')
                output.write(chunk)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    if written == 0:
        destination.unlink(missing_ok=True)
        raise ValueError('The branding image is empty')
    return filename


def homepage_branding_path(tenant_id, filename: str) -> Path:
    if not filename or Path(filename).name != filename:
        raise ValueError('Invalid branding filename')
    if not filename.startswith(('banner-', 'logo-')):
        raise ValueError('Invalid branding filename')
    return _asset_root(tenant_id) / filename


def delete_homepage_branding_image(tenant_id, filename: str | None) -> None:
    if not filename:
        return
    try:
        homepage_branding_path(tenant_id, filename).unlink(missing_ok=True)
    except ValueError:
        return
