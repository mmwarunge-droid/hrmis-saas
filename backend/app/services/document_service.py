import hashlib

from flask_jwt_extended import current_user

from app.extensions import db
from app.models import Document, Employee
from app.services.audit_service import log_event
from app.utils.file_storage import save_document_file


def _checksum(path: str) -> str:
    sha = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def can_access_document(user, document: Document) -> bool:
    if user.has_role('SUPER_ADMIN'):
        return True
    if str(user.tenant_id) != str(document.tenant_id):
        return False
    if user.has_any_role({'HR_CONSULTANT', 'CLIENT_ADMIN'}):
        return True
    if user.has_role('MANAGER'):
        return document.access_level in {'manager', 'employee'}
    if user.has_role('EMPLOYEE'):
        return user.employee_profile and str(user.employee_profile.id) == str(document.employee_id) and document.access_level == 'employee'
    return False


def create_document(payload, file, tenant_id):
    employee_id = payload.get('employee_id')
    if employee_id and not Employee.query.filter_by(id=employee_id, tenant_id=tenant_id, deleted_at=None).first():
        raise ValueError('employee_id is invalid for this tenant')
    stored = save_document_file(file, tenant_id)
    checksum = _checksum(stored['file_path'])
    document = Document(
        tenant_id=tenant_id,
        uploaded_by_id=current_user.id,
        checksum_sha256=checksum,
        **payload,
        **stored,
    )
    db.session.add(document)
    db.session.flush()
    log_event('document.upload', 'Document', document.id, tenant_id=tenant_id, metadata={'filename': document.original_filename})
    db.session.commit()
    return document


def update_document(document, payload):
    for key, value in payload.items():
        setattr(document, key, value)
    log_event('document.update', 'Document', document.id, tenant_id=document.tenant_id)
    db.session.commit()
    return document
