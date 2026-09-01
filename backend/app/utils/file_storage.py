from pathlib import Path
from uuid import uuid4

from flask import current_app, send_file
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'txt'}
ALLOWED_MIME_PREFIXES = ('application/', 'image/', 'text/plain')

ONBOARDING_DOCUMENT_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt'}
ONBOARDING_VIDEO_EXTENSIONS = {'mp4', 'webm'}


def detect_mp4_duration(file_path: str):
    """Return MP4 duration in seconds from the movie header when available."""
    path = Path(file_path)

    def box_header(stream, container_end):
        start = stream.tell()
        header = stream.read(8)
        if len(header) != 8:
            return None

        size = int.from_bytes(header[:4], 'big')
        box_type = header[4:8]
        header_size = 8

        if size == 1:
            extended = stream.read(8)
            if len(extended) != 8:
                return None
            size = int.from_bytes(extended, 'big')
            header_size = 16
        elif size == 0:
            size = container_end - start

        if size < header_size or start + size > container_end:
            return None
        return box_type, stream.tell(), start + size

    try:
        with path.open('rb') as stream:
            file_end = path.stat().st_size
            moov = None

            while stream.tell() + 8 <= file_end:
                header = box_header(stream, file_end)
                if not header:
                    return None
                box_type, data_start, box_end = header
                if box_type == b'moov':
                    moov = (data_start, box_end)
                    break
                stream.seek(box_end)

            if not moov:
                return None

            stream.seek(moov[0])
            while stream.tell() + 8 <= moov[1]:
                header = box_header(stream, moov[1])
                if not header:
                    return None
                box_type, data_start, box_end = header
                if box_type != b'mvhd':
                    stream.seek(box_end)
                    continue

                stream.seek(data_start)
                version_flags = stream.read(4)
                if len(version_flags) != 4:
                    return None
                version = version_flags[0]

                if version == 0:
                    stream.seek(8, 1)
                    timescale_bytes = stream.read(4)
                    duration_bytes = stream.read(4)
                elif version == 1:
                    stream.seek(16, 1)
                    timescale_bytes = stream.read(4)
                    duration_bytes = stream.read(8)
                else:
                    return None

                if not timescale_bytes or not duration_bytes:
                    return None
                timescale = int.from_bytes(timescale_bytes, 'big')
                duration = int.from_bytes(duration_bytes, 'big')
                if timescale <= 0 or duration <= 0:
                    return None
                return duration / timescale
    except (OSError, ValueError):
        return None

    return None


def _extension(filename: str) -> str:
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''


def validate_upload(file: FileStorage):
    if not file or not file.filename:
        raise ValueError('No file was uploaded')
    ext = _extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f'File type .{ext} is not allowed')
    if file.mimetype and not (file.mimetype.startswith(ALLOWED_MIME_PREFIXES) or file.mimetype in {'application/pdf'}):
        raise ValueError('Unsupported file MIME type')


def save_document_file(file: FileStorage, tenant_id: str) -> dict:
    validate_upload(file)
    original = secure_filename(file.filename)
    ext = _extension(original)
    stored_name = f'{uuid4().hex}.{ext}'
    folder = Path(current_app.config['UPLOAD_FOLDER']) / str(tenant_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / stored_name
    file.save(path)
    return {
        'original_filename': original,
        'stored_filename': stored_name,
        'file_path': str(path),
        'mime_type': file.mimetype,
        'size_bytes': path.stat().st_size,
    }


def save_onboarding_resource_file(file: FileStorage, tenant_id: str) -> dict:
    if not file or not file.filename:
        raise ValueError('No training resource was uploaded')

    original = secure_filename(file.filename)
    ext = _extension(original)

    if ext in ONBOARDING_DOCUMENT_EXTENSIONS:
        resource_type = 'document'
    elif ext in ONBOARDING_VIDEO_EXTENSIONS:
        resource_type = 'video'
    else:
        allowed = sorted(
            ONBOARDING_DOCUMENT_EXTENSIONS | ONBOARDING_VIDEO_EXTENSIONS
        )
        raise ValueError(
            f'Unsupported training resource type. Allowed: {", ".join(allowed)}'
        )

    if resource_type == 'video' and file.mimetype and not file.mimetype.startswith('video/'):
        raise ValueError('Training video must use a video MIME type')

    if (
        resource_type == 'document'
        and file.mimetype
        and not (
            file.mimetype.startswith('application/')
            or file.mimetype == 'text/plain'
        )
    ):
        raise ValueError('Training document has an unsupported MIME type')

    stored_name = f'{uuid4().hex}.{ext}'
    folder = (
        Path(current_app.config['UPLOAD_FOLDER'])
        / str(tenant_id)
        / 'onboarding'
    )
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / stored_name
    file.save(path)

    return {
        'resource_type': resource_type,
        'original_filename': original,
        'stored_filename': stored_name,
        'file_path': str(path),
        'mime_type': file.mimetype,
        'size_bytes': path.stat().st_size,
        'detected_duration_seconds': (
            detect_mp4_duration(str(path))
            if resource_type == 'video' and ext == 'mp4'
            else None
        ),
    }


def send_stored_file(file_path: str, download_name: str, *, as_attachment=True, mimetype=None):
    path = Path(file_path)
    upload_root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    resolved = path.resolve()
    if upload_root not in resolved.parents and resolved != upload_root:
        raise ValueError('Invalid file path')
    if not resolved.exists():
        raise FileNotFoundError('File does not exist')
    return send_file(
        resolved,
        as_attachment=as_attachment,
        download_name=download_name,
        mimetype=mimetype,
        conditional=True,
    )
