from pathlib import Path
from uuid import uuid4

from flask import current_app, send_file
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx', 'xls', 'xlsx', 'png', 'jpg', 'jpeg', 'txt'}
ALLOWED_MIME_PREFIXES = ('application/', 'image/', 'text/plain')


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


def send_stored_file(file_path: str, download_name: str):
    path = Path(file_path)
    upload_root = Path(current_app.config['UPLOAD_FOLDER']).resolve()
    resolved = path.resolve()
    if upload_root not in resolved.parents and resolved != upload_root:
        raise ValueError('Invalid file path')
    if not resolved.exists():
        raise FileNotFoundError('File does not exist')
    return send_file(resolved, as_attachment=True, download_name=download_name)
