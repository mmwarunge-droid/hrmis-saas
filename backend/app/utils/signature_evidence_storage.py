import hashlib
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def _evidence_root():
    root = Path(
        current_app.config['SIGNATURE_EVIDENCE_FOLDER'],
    )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def save_signature_artifact(
    content,
    *,
    tenant_id,
    signature_request_id,
    filename,
):
    if not isinstance(content, bytes) or not content:
        raise ValueError(
            'Signature evidence content must be non-empty bytes.',
        )

    original_filename = secure_filename(filename)

    if not original_filename:
        raise ValueError(
            'Signature evidence filename is invalid.',
        )

    suffix = Path(original_filename).suffix.lower()
    stored_filename = f'{uuid4().hex}{suffix}'
    folder = (
        _evidence_root()
        / str(tenant_id)
        / str(signature_request_id)
    )
    folder.mkdir(parents=True, exist_ok=True)

    file_path = folder / stored_filename
    file_path.write_bytes(content)

    return {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'file_path': str(file_path),
        'size_bytes': len(content),
        'checksum_sha256': hashlib.sha256(content).hexdigest(),
    }


def validate_signature_artifact_path(file_path):
    root = _evidence_root()
    resolved = Path(file_path).resolve()

    if root not in resolved.parents:
        raise ValueError('Invalid signature artifact path')

    if not resolved.exists():
        raise FileNotFoundError(
            'Signature artifact does not exist',
        )

    return resolved
