import hashlib
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


def _storage_backend():
    return current_app.config.get(
        'SIGNATURE_EVIDENCE_STORAGE',
        'local',
    ).strip().lower()


def _evidence_root():
    root = Path(
        current_app.config['SIGNATURE_EVIDENCE_FOLDER'],
    )
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_filename(filename):
    original_filename = secure_filename(filename)

    if not original_filename:
        raise ValueError(
            'Signature evidence filename is invalid.',
        )

    return original_filename


def _artifact_key(
    *,
    tenant_id,
    signature_request_id,
    stored_filename,
):
    prefix = current_app.config.get(
        'SIGNATURE_EVIDENCE_S3_PREFIX',
        'signature-evidence',
    ).strip('/')

    parts = [
        part
        for part in (
            prefix,
            str(tenant_id),
            str(signature_request_id),
            stored_filename,
        )
        if part
    ]
    return '/'.join(parts)


def _s3_client():
    try:
        import boto3
    except ImportError as exc:
        raise RuntimeError(
            'boto3 is required for S3 signature evidence storage.',
        ) from exc

    return boto3.client(
        's3',
        region_name=current_app.config.get(
            'SIGNATURE_EVIDENCE_S3_REGION',
        ),
        endpoint_url=current_app.config.get(
            'SIGNATURE_EVIDENCE_S3_ENDPOINT_URL',
        ),
        aws_access_key_id=current_app.config.get(
            'SIGNATURE_EVIDENCE_S3_ACCESS_KEY_ID',
        ),
        aws_secret_access_key=current_app.config.get(
            'SIGNATURE_EVIDENCE_S3_SECRET_ACCESS_KEY',
        ),
    )


def _s3_location(key):
    bucket = current_app.config.get(
        'SIGNATURE_EVIDENCE_S3_BUCKET',
    )

    if not bucket:
        raise RuntimeError(
            'SIGNATURE_EVIDENCE_S3_BUCKET is required.',
        )

    return bucket, f's3://{bucket}/{key}'


def save_signature_artifact(
    content,
    *,
    tenant_id,
    signature_request_id,
    filename,
    mime_type='application/octet-stream',
):
    if not isinstance(content, bytes) or not content:
        raise ValueError(
            'Signature evidence content must be non-empty bytes.',
        )

    original_filename = _safe_filename(filename)
    suffix = Path(original_filename).suffix.lower()
    stored_filename = f'{uuid4().hex}{suffix}'
    checksum = hashlib.sha256(content).hexdigest()

    if _storage_backend() == 's3':
        key = _artifact_key(
            tenant_id=tenant_id,
            signature_request_id=signature_request_id,
            stored_filename=stored_filename,
        )
        bucket, file_path = _s3_location(key)
        payload = {
            'Bucket': bucket,
            'Key': key,
            'Body': content,
            'ContentType': mime_type,
            'Metadata': {
                'sha256': checksum,
                'tenant-id': str(tenant_id),
                'signature-request-id': str(
                    signature_request_id,
                ),
            },
        }
        server_side_encryption = current_app.config.get(
            'SIGNATURE_EVIDENCE_S3_SSE',
        )
        if server_side_encryption:
            payload['ServerSideEncryption'] = (
                server_side_encryption
            )
        _s3_client().put_object(**payload)
    else:
        folder = (
            _evidence_root()
            / str(tenant_id)
            / str(signature_request_id)
        )
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / stored_filename
        path.write_bytes(content)
        file_path = str(path)

    return {
        'original_filename': original_filename,
        'stored_filename': stored_filename,
        'file_path': file_path,
        'size_bytes': len(content),
        'checksum_sha256': checksum,
    }


def _parse_s3_path(file_path):
    parsed = urlparse(file_path)

    if parsed.scheme != 's3' or not parsed.netloc:
        raise ValueError('Invalid S3 signature artifact path')

    key = parsed.path.lstrip('/')

    if not key:
        raise ValueError('Invalid S3 signature artifact path')

    expected_bucket = current_app.config.get(
        'SIGNATURE_EVIDENCE_S3_BUCKET',
    )

    if expected_bucket and parsed.netloc != expected_bucket:
        raise ValueError('Invalid signature artifact bucket')

    expected_prefix = current_app.config.get(
        'SIGNATURE_EVIDENCE_S3_PREFIX',
        'signature-evidence',
    ).strip('/')

    if expected_prefix and not (
        key == expected_prefix
        or key.startswith(f'{expected_prefix}/')
    ):
        raise ValueError('Invalid signature artifact key')

    return parsed.netloc, key


def validate_signature_artifact_path(file_path):
    if str(file_path).startswith('s3://'):
        _parse_s3_path(str(file_path))
        return str(file_path)

    root = _evidence_root()
    resolved = Path(file_path).resolve()

    if root not in resolved.parents:
        raise ValueError('Invalid signature artifact path')

    if not resolved.exists():
        raise FileNotFoundError(
            'Signature artifact does not exist',
        )

    return resolved


def read_signature_artifact(file_path):
    validated = validate_signature_artifact_path(file_path)

    if isinstance(validated, Path):
        return validated.read_bytes()

    bucket, key = _parse_s3_path(validated)
    response = _s3_client().get_object(
        Bucket=bucket,
        Key=key,
    )
    return response['Body'].read()


def delete_signature_artifact(file_path):
    if str(file_path).startswith('s3://'):
        bucket, key = _parse_s3_path(str(file_path))
        _s3_client().delete_object(
            Bucket=bucket,
            Key=key,
        )
        return

    validated = validate_signature_artifact_path(file_path)
    validated.unlink(missing_ok=True)
